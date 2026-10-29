"""Run explicitly on the Docker host. Tokens are never printed or sent over HTTP."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import tempfile


def provision(keys_path, connector, output_path):
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,63}', connector):
        raise ValueError('Invalid connector ID')
    if os.getuid() != 1000:
        raise ValueError('Run as host UID 1000 so the connector and Atlas can read the secret files')
    keys_path, output_path = Path(keys_path), Path(output_path)
    if keys_path.resolve() == output_path.resolve() or keys_path.is_symlink() or output_path.is_symlink():
        raise ValueError('Choose distinct regular key and token file paths')
    keys = json.loads(keys_path.read_text()) if keys_path.exists() else {}
    if not isinstance(keys, dict) or any(not isinstance(v, str) or len(v) < 32 for v in keys.values()):
        raise ValueError('Existing keys file is invalid; it has not been changed')
    token = keys.get(connector) or secrets.token_urlsafe(48)
    if output_path.exists() and output_path.read_text().strip() != token:
        raise ValueError('Output token differs from the host key; use a new output path')
    keys[connector] = token
    for path, value in ((output_path, token+'\n'), (keys_path, json.dumps(keys, indent=2)+'\n')):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
            f.write(value)
            temporary = Path(f.name)
        temporary.chmod(0o600)
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--keys', required=True)
    parser.add_argument('--connector', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        provision(args.keys, args.connector, args.output)
    except (OSError, ValueError) as error:
        raise SystemExit('Token setup failed: '+str(error)) from None
    print('Source token prepared. Recreate Atlas to reload the mounted keys file.')
