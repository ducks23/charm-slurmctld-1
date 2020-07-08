#! /usr/bin/env python3
import collections
import logging
import socket
import json


from ops.charm import CharmBase

from ops.main import main

from ops.framework import (
    Object,
    ObjectEvents,
    StoredState,
)

from slurm_ops_manager import (
    SlurmConfig,
    SlurmOpsManager,
)


logger = logging.getLogger()


def dict_keys_without_hyphens(a_dict):
    """Return the a new dict with underscores instead of hyphens in keys.
    https://github.com/juju/charm-helpers/blob/f9c06a96b0d1587a1c94d4d398efde8a403026eb/charmhelpers/contrib/templating/contexts.py#L31,L34
    """
    return dict(
        (key.replace('-', '_'), val) for key, val in a_dict.items())


class SlurmClusterProviderRelationEvents(ObjectEvents):
    """ SlurmClusterProviderRelationEvents"""


class SlurmClusterProviderRelation(Object):

    on = SlurmClusterProviderRelationEvents()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)

        self.charm = charm
        self._relation_name = relation_name

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

    def get_partitions(self):
        return self._partitions

    def get_slurmd_node_data(self):
        return self._slurmd_node_data

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

        if self.charm.slurmdbd.slurmdbd_host_port_acquired:
            addr = event.relation.data[self.model.unit]['ingress-address']
            slurmctld_host_port_addr = {
                'active_slurmctld_hostname': self.charm.slurm_ops_manager.hostname,
                'slurmctld_port': self.charm.slurm_ops_manager.port,
                'active_slurmctld_ingress_address': addr,
            }
            slurm_config = json.dumps({
                **slurmctld_host_port_addr,
                **self.charm.slurmdbd.host_port_addr,
                **self.charm.model.config,
                **self._slurmd_node_data,
            })
           
            event.relation.data[self.model.app]['slurm_config'] = slurm_config

            self.charm.slurm_ops_manager.on.render_config_and_restart.emit(
                SlurmConfig(slurm_config)
            )

        else:
            self.charm.unit.status = BlockedStatus("Need relation to slurmdbd")
            event.defer()
            return

    def _on_relation_departed(self, event):
        logger.debug("################ LOGGING RELATION DEPARTED ####################")

    def _on_relation_broken(self, event):
        logger.debug("################ LOGGING RELATION BROKEN ####################")


class SlurmdbdRequiresRelation(Object):

    _state = StoredState()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)

        self.charm = charm
        self._relation_name = relation_name

        self._state.set_default(slurmdbd_host_port_acquired=False)
        self._state.set_default(slurmdbd_host_port_addr=dict())

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

    @property
    def slurmdbd_host_port_acquired(self):
        return self._state.slurmdbd_host_port_acquired

    def slurmdbd_host_port_acquired(self):
        return self._state.slurmdbd_host_port_addr

    def _on_relation_created(self, event):
        logger.debug("################ LOGGING RELATION CREATED ####################")

    def _on_relation_joined(self, event):
        logger.debug("################ LOGGING RELATION JOINED ####################")

    def _on_relation_changed(self, event):
        logger.debug("################ LOGGING RELATION CHANGED ####################")

        self._state.dbd_ingress_address = event.relation.data[event.unit]['ingress-address']
        self._state.dbd_hostname = self.charm.slurm_ops_manager.hostname
        self._state.dbd_port = self.charm.slurm_ops_manager.port
        self._state.slurmdbd_host_port_addr = {
            'slurmdbd_ingress_address': event.relation.data[event.unit]['ingress-address'],
            'slurm_dbd_hostname': event.relation.data[event.unit]['hostname'],
            'slurmdbd_port': event.relation.data[event.unit]['port'],
        }
        self._state.slurmdbd_host_port_acquired = True

    def _on_relation_departed(self, event):
        logger.debug("################ LOGGING RELATION DEPARTED ####################")

    def _on_relation_broken(self, event):
        logger.debug("################ LOGGING RELATION BROKEN ####################")


class SlumctldCharm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)

        self.slurm_ops_manager = SlurmOpsManager(self, "slurmctld")

        self.slurmdbd = SlurmdbdRequires(self, "slurmdbd")
        self.slurm_cluster = SlurmClusterProviderRelation(self, "slurm-cluster")
        
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)

    def _on_install(self, event):
        self.slurm_ops_manage.prepare_system_for_slurm()

    def _on_start(self, event):
        self.unit.status = ActiveStatus("Slurmctld Available")


if __name__ == "__main__":
    main(RequirerCharm)
