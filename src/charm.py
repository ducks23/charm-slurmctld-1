#! /usr/bin/env python3
import collections
import json
import logging

from ops.charm import CharmBase

from ops.main import main

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
    StoredState,
)

from ops.model import (
    ActiveStatus,
    BlockedStatus,
)

from slurm_ops_manager import SlurmOpsManager

#from interface_slurmd import SlurmdRequiresRelation

from interface_slurmdbd import SlurmdbdRequiresRelation


logger = logging.getLogger()


def dict_keys_without_hyphens(a_dict):
    """Return the a new dict with underscores instead of hyphens in keys.
    https://github.com/juju/charm-helpers/blob/f9c06a96b0d1587a1c94d4d398efde8a403026eb/charmhelpers/contrib/templating/contexts.py#L31,L34
    """
    return dict(
        (key.replace('-', '_'), val) for key, val in a_dict.items())


class SlurmdUnAvailableEvent(EventBase):
    """Emmited when the slurmd relation is broken."""


class SlurmdAvailableEvent(EventBase):
    """Emmited when slurmd is available."""


class SlurmdRequiresEvents(ObjectEvents):
    """ SlurmClusterProviderRelationEvents"""
    slurmd_available = EventSource(SlurmdAvailableEvent)
    slurmd_unavailable = EventSource(SlurmdUnAvailableEvent)


class SlurmdRequiresRelation(Object):

    on = SlurmdRequiresEvents()

    _state = StoredState()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)

        self.charm = charm
        self._relation_name = relation_name

        self._state.set_default(slurmd_acquired=False)
        self._state.set_default(slurm_config=str())

        self.framework.observe(
            charm.on[self._relation_name].relation_created,
            self._on_relation_created
        )

        self.framework.observe(
            charm.on[self._relation_name].relation_joined,
            self._on_relation_joined
        )

        self.framework.observe(
            charm.on[self._relation_name].relation_changed,
            self._on_relation_changed
        )

        self.framework.observe(
            charm.on[self._relation_name].relation_departed,
            self._on_relation_departed
        )

        self.framework.observe(
            charm.on[self._relation_name].relation_broken,
            self._on_relation_broken
        )

    def get_slurm_config(self):
        return self._state.slurm_config

    def slurmd_acquired(self):
        return self._state.slurmd_acquired

    @property
    def _partitions(self):
        """Parses self._self.node_data and returns the partitions
        with associated nodes.
        """
        part_dict = collections.defaultdict(dict)
        for node in self._slurmd_node_data:
            part_dict[node['partition']].setdefault('hosts', [])
            part_dict[node['partition']]['hosts'].append(node['hostname'])
            part_dict[node['partition']]['default'] = node['default']
        return dict(part_dict)

    @property
    def _slurmd_node_data(self):
        """Returns the node info for units for all slurmd
        relations.
        """
        relations = self.framework.model.relations['slurmd']

        node_info_keys = [
            'ingress-address',
            'hostname',
            'partition',
            'inventory',
            'default',
        ]

        nodes_info = list()
        for relation in relations:
            for unit in relation.units:
                nodes_info.append(dict_keys_without_hyphens({
                    k: relation.data[unit][k]
                    for k in node_info_keys
                }))
        return nodes_info

    def _on_relation_created(self, event):
        logger.debug("################ LOGGING RELATION CREATED ####################")

    def _on_relation_joined(self, event):
        logger.debug("################ LOGGING RELATION JOINED ####################")

    def _on_relation_changed(self, event):
        logger.debug("################ LOGGING RELATION CHANGED ####################")

        if self.charm.slurmdbd.slurmdbd_acquired:

            relation_unit_data = event.relation.data[self.model.unit]
            slurmdbd_info = json.loads(self.charm.slurmdbd.get_slurmdbd_info())

            slurm_config = json.dumps({
                'nodes': self._slurmd_node_data,
                'partitions': self._partitions,
                'slurmdbd_port': slurmdbd_info['port'],
                'slurmdbd_hostname': slurmdbd_info['hostname'],
                'slurmdbd_ingress_address': slurmdbd_info['ingress_address'],
                'active_slurmctld_hostname': self.charm.slurm_ops_manager.hostname,
                'active_slurmctld_ingress_address': relation_unit_data['ingress-address'],
                'slurmctld_port': self.charm.slurm_ops_manager.port,
                **self.model.config,
            })

            event.relation.data[self.model.app]['slurm_config'] = slurm_config
            self.charm.slurm_ops_manager.on.render_config_and_restart.emit(slurm_config)
            self._state.slurm_config = slurm_config
            self._state.slurmd_acquired = True
        else:
            self.charm.unit.status = BlockedStatus("Need relation to slurmdbd")
            event.defer()
            return

    def _on_relation_departed(self, event):
        logger.debug("################ LOGGING RELATION DEPARTED ####################")

    def _on_relation_broken(self, event):
        logger.debug("################ LOGGING RELATION BROKEN ####################")
        self._state.slurmd_acquired = False
        self.on.slurmd_unavailable.emit()


class SlurmctldCharm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)

        self.slurm_ops_manager = SlurmOpsManager(self, "slurmctld")

        self.slurmdbd = SlurmdbdRequiresRelation(self, "slurmdbd")
        self.slurmd = SlurmdRequiresRelation(self, "slurmd")
        
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_check_status_and_write_config)

        self.framework.observe(self.slurmdbd.on.slurmdbd_available, self._on_check_status_and_write_config)
        self.framework.observe(self.slurmd.on.slurmd_available, self._on_check_status_and_write_config)
        self.framework.observe(self.slurmd.on.slurmd_unavailable, self._on_check_status_and_write_config)

    def _on_install(self, event):
        self.slurm_ops_manager.prepare_system_for_slurm()
        self.unit.status = ActiveStatus("Slurm Installed")

    def _on_check_status_and_write_config(self, event):
        if not (self.slurmdbd.slurmdbd_acquired and self.slurmd.slurmd_acquired):
            if not self.slurmdbd.slurmdbd_acquired:
                self.unit.status = BlockedStatus("Slurm NOT AVAILABLE - NEED RELATION TO SLURMDBD")
            else:
                self.unit.status = BlockedStatus("Slurm NOT AVAILABLE - NEED RELATION TO SLURMD")
            event.defer()
        else:
            slurm_config = self.slurmd.get_slurm_config()
            self.slurm_ops_manager.on.configure_and_restart.emit(slurm_config)
            logger.debug(slurm_config)
            self.unit.status = ActiveStatus("Slurmctld Available")


if __name__ == "__main__":
    main(SlurmctldCharm)
