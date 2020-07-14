# charm-slurmctld
  
![alt text](.github/slurm.png)

<p align="center"><b>This is The Slurmctld charm for The Slurm Workload Manager</b>, <i>"The Slurm Workload Manager (formerly known as Simple Linux Utility for Resource Management or SLURM), or Slurm, is a free and open-source job scheduler for Linux and Unix-like kernels, used by many of the world's supercomputers and computer clusters."</i></p>

Requirements
------------
- Ubuntu 20.04
- juju 2.8.1
- charmcraft

Quickstart
----------

```bash
charmcraft build
juju deploy ./slurmctld.charm --resource slurm=/path/to/slurm/binary/
juju relate slurmd slurmctld
juju relate slurmdbd slurmctld
```

Interfaces
----------
- https://github.com/omnivector-solutions/interface-slurmd
- https://github.com/omnivector-solutions/ops-interface-slurmdbd

Components
----------
- https://github.com/omnivector-solutions/slurm-ops-manager
