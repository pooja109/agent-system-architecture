import os
import time
import tempfile
from datetime import datetime, timedelta

from azure.storage.blob import (
    BlobServiceClient,
    BlobClient,
    ContainerClient,
    generate_blob_sas,
    BlobSasPermissions
)
from md2pdf import md2pdf

class BlobCopier:
    def __init__(
        self,
        conn_str: str,
        container_name: str,
        source_dir: str,
        dest_base_dir: str,
        poll_interval: int = 2
    ):
        self.service_client = BlobServiceClient.from_connection_string(conn_str)
        self.container_name = container_name
        self.container_client: ContainerClient = self.service_client.get_container_client(container_name)
        self.source_dir = source_dir.rstrip("/") + "/"
        self.dest_base_dir = dest_base_dir.rstrip("/")
        self.poll_interval = poll_interval

        # retrieve account key for SAS generation (works only with key-based auth)
        cred = self.service_client.credential
        self.account_key = getattr(cred, 'account_key', None)

    def build_sas_token(self, blob_name: str) -> str:
        if not self.account_key:
            raise RuntimeError("Account key is required for SAS generation")
        sas = generate_blob_sas(
            account_name=self.service_client.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        return sas

    def copy_all(self):
        for blob_props in self.container_client.list_blobs(name_starts_with=self.source_dir):
            src_path = blob_props.name
            filename = os.path.basename(src_path)

            if "_" not in filename:
                print(f"Skipping unexpected filename format: {filename}")
                continue

            customer_id = filename.split("_", 1)[0]
            dest_dir = f"{self.dest_base_dir}/{customer_id}/research_output"
            dest_path = f"{dest_dir}/{filename}"

            src_blob: BlobClient = self.service_client.get_blob_client(
                container=self.container_name,
                blob=src_path
            )
            dest_blob: BlobClient = self.service_client.get_blob_client(
                container=self.container_name,
                blob=dest_path
            )

            # Remove existing destination blob to ensure overwrite
            try:
                dest_blob.delete_blob()
                print(f"Deleted existing blob at {dest_path}")
            except Exception:
                pass

            # Generate SAS for source URL (or use public URL if accessible)
            try:
                sas_token = self.build_sas_token(src_path)
                source_url = f"{src_blob.url}?{sas_token}"
            except RuntimeError:
                source_url = src_blob.url

            # Initiate copy
            copy_props = dest_blob.start_copy_from_url(source_url)
            print(f"Started copy: {src_path} -> {dest_path} (Copy ID: {copy_props['copy_id']})")

            # Poll status until complete
            while True:
                props = dest_blob.get_blob_properties()
                status = props.copy.status
                print(f"Copy status for {dest_path}: {status}")
                if status.lower() != 'pending':
                    if status.lower() == 'success':
                        print(f"Copy succeeded for {dest_path}")

                        # If markdown, convert to PDF
                        if filename.lower().endswith('.md'):
                            self.convert_and_upload_pdf(dest_dir, filename)
                    else:
                        print(f"Copy failed for {dest_path}, status: {status}")
                    break
                time.sleep(self.poll_interval)

    def convert_and_upload_pdf(self, dest_dir: str, filename: str):
        blob_client = self.service_client.get_blob_client(
            container=self.container_name,
            blob=f"{dest_dir}/{filename}"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = os.path.join(tmpdir, filename)
            pdf_name = f"{os.path.splitext(filename)[0]}.pdf"
            pdf_path = os.path.join(tmpdir, pdf_name)
            data = blob_client.download_blob().readall()
            # Download markdown
            # with open(md_path, 'wb') as f:
            #     data = blob_client.download_blob().readall()
            #     f.write(data)
            curdir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(curdir, "markdown.css")
            print(f"Converting {filename} to PDF using md2pdf...")
            try:
                # Convert using md2pdf library
                md2pdf(pdf_path, data, css_file_path=css_path)
                
                print(f"Conversion complete: {pdf_name}")

                # Upload PDF, overwrite if exists
                pdf_blob_path = f"{dest_dir}/{pdf_name}"
                pdf_blob: BlobClient = self.service_client.get_blob_client(
                    container=self.container_name,
                    blob=pdf_blob_path
                )
                with open(pdf_path, 'rb') as f:
                    pdf_blob.upload_blob(f, overwrite=True)
                print(f"Uploaded PDF to {pdf_blob_path}")
            except Exception as e:
                print(f"Failed to convert/upload PDF for {filename}: {e}")


def main():
    # Configuration
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise ValueError("Environment variable AZURE_STORAGE_CONNECTION_STRING must be set")

    container = "lowtouch"
    source_dir = "research_output/20250703"
    dest_base = "20250707"

    copier = BlobCopier(
        conn_str,
        container,
        source_dir,
        dest_base,
        poll_interval=5
    )
    copier.copy_all()


if __name__ == "__main__":
    main()
