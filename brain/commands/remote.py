import typer

from brain.remote import add_remote, get_remote, list_remotes, remove_remote


def run_remote_add(
    name: str,
    bucket: str,
    prefix: str,
    endpoint: str,
    key_id: str | None,
    secret: str | None,
) -> None:
    add_remote(name, bucket, prefix, endpoint, key_id, secret)
    cred_note = (
        "credentials stored in keyring" if key_id else "using boto3 default credential chain"
    )
    print(f"Remote '{name}' added ({cred_note}).")
    print(f"  bucket:   {bucket}")
    if prefix:
        print(f"  prefix:   {prefix}")
    print(f"  endpoint: {endpoint}")


def run_remote_list() -> None:
    names = list_remotes()
    if not names:
        print("No remotes configured. Use 'brain remote add' to add one.")
        return
    print(f"{'NAME':<20} {'BUCKET':<30} {'ENDPOINT'}")
    print("-" * 80)
    for name in names:
        try:
            cfg = get_remote(name)
            bucket_col = cfg.bucket
            if cfg.prefix:
                bucket_col += f"/{cfg.prefix.rstrip('/')}"
            creds = "[keyring]" if cfg.key_id else "[default chain]"
            print(f"{name:<20} {bucket_col:<30} {cfg.endpoint}  {creds}")
        except Exception as e:
            print(f"{name:<20} (error reading config: {e})")


def run_remote_remove(name: str) -> None:
    try:
        get_remote(name)
    except KeyError:
        typer.echo(f"Error: remote '{name}' not found.", err=True)
        raise typer.Exit(1) from None
    remove_remote(name)
    print(f"Remote '{name}' removed.")
