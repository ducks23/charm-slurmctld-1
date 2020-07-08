#! /usr/bin/env python3
from ops.charm import CharmBase

from ops.main import main

from slurm_ops_manager import SlurmOpsManager

from interface_slurm_cluster import SlurmClusterProvidesRelation

from interface_slurmdbd import SlurmdbdRequiresRelation


class SlurmctldCharm(CharmBase):

    def __init__(self, *args):
        super().__init__(*args)

        self.slurm_ops_manager = SlurmOpsManager(self, "slurmctld")

        self.slurmdbd = SlurmdbdRequiresRelation(self, "slurmdbd")
        self.slurm_cluster = SlurmClusterProvidesRelation(self, "slurm-cluster")
        
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)

    def _on_install(self, event):
        self.slurm_ops_manage.prepare_system_for_slurm()

    def _on_start(self, event):
        self.unit.status = ActiveStatus("Slurmctld Available")


if __name__ == "__main__":
    main(SlurmctldCharm)
