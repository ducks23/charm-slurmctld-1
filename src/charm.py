#! /usr/bin/env python3
"""libraries needed for charm."""
import json
import logging

from interface_slurmd import SlurmdRequires
from interface_slurmdbd import SlurmdbdRequiresRelation
from ops.charm import CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
)
from slurm_ops_manager import SlurmOpsManager

logger = logging.getLogger()


class SlurmctldCharm(CharmBase):
    """Charm to represent the controller node of The Slurm Workload Manager."""

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        self.slurm_ops_manager = SlurmOpsManager(self, "slurmctld")
        self.slurmdbd = SlurmdbdRequiresRelation(self, "slurmdbd")
        self.slurmd = SlurmdRequires(self, "slurmd")

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
            try:
                slurm_config = json.loads(self.slurmd.get_slurm_config())
            except json.JSONDecodeError as e:
                logger.debug(e)

            self.slurm_ops_manager.render_config_and_restart(slurm_config)
            logger.debug(slurm_config)
            self.unit.status = ActiveStatus("Slurmctld Available")


if __name__ == "__main__":
    main(SlurmctldCharm)
