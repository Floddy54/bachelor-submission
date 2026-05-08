from pathlib import Path
from azure.storage.blob import BlobServiceClient

conn = Path(".secrets/azure_connection_string").read_text().strip()
svc  = BlobServiceClient.from_connection_string(conn)
cli  = svc.get_container_client("anti-bad")
blob = cli.get_blob_client("smoke/hello.txt")
blob.upload_blob(b"hello from laptop", overwrite=True)
print("uploaded. listing:")
for b in cli.list_blobs(name_starts_with="smoke/"):
    print(" ", b.name, b.size, "bytes")
