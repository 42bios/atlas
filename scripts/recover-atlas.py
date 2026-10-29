#!/usr/bin/env python3
"""Validate/rehearse a protected Atlas-data archive into a new directory only."""
import argparse
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from atlas_modules.settings.backups import HostBackups

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--restore-to',type=Path,help='New, nonexistent directory; existing installations are never overwritten')
    args=parser.parse_args()
    backups=HostBackups(server.application)
    backups.root=args.archive.resolve().parent
    backups.scratch=Path(tempfile.gettempdir())
    result=backups.validate(args.archive.name,args.restore_to)
    print('Backup verified: %d files, %d systems, %d devices.'%(result['files'],result['connections'],result['inventory']['devices']))
    if args.restore_to:print('Restored private Atlas data into the new directory. Keep it private; configure deployment mounts before starting Atlas.')
    print(result['scope'])

if __name__=='__main__':main()
