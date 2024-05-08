# Downloads the latest artifact from a GitHub repository
#
# curl -L \
#   -H "Accept: application/vnd.github+json" \
#   -H "Authorization: Bearer <YOUR-TOKEN>" \
#   -H "X-GitHub-Api-Version: 2022-11-28" \
#   https://api.github.com/repos/OWNER/REPO/actions/artifacts
import urllib.request
import json
from pathlib import Path
import zipfile


class Repository:
    def __init__(self, token, owner, repo):
        """
        token: GitHub Personal Access Token
        owner: GitHub repository owner
        repo: GitHub repository name
        """
        self.token = token
        self.owner = owner
        self.repo = repo
    
    def list_artifacts(self, per_page=30, page=1, name=None):
        """
        per_page: The number of results per page (max 100).
        page: Page number of the results to fetch.
        name: Filters artifacts by exact match on their name field.
        """
        if per_page > 100:
            raise ValueError('per_page must be less than or equal to 100.')
        if per_page < 1:
            raise ValueError('per_page must be greater than 0.')
        
        headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {self.token}',
            'X-GitHub-Api-Version': '2022-11-28'
        }

        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/artifacts?per_page={per_page}&page={page}'
        if name:
            url += f'&name={name}'
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as res:
            body = json.loads(res.read())
        
        return body

    def get_artifacts(self, artifact_id):
        """
        Gets a specific artifact for a workflow run. Anyone with read access to the repository 
        can use this endpoint. If the repository is private you must use an access token with 
        the repo scope. GitHub Apps must have the actions:read permission to use this endpoint.
        """
        headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {self.token}',
            'X-GitHub-Api-Version': '2022-11-28'
        }

        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/artifacts/{artifact_id}'
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as res:
            body = json.loads(res.read())
        
        return body

    def download_artifact(self, artifact_id, archive_format='zip', save_dir='./gh_artifacts', save_name=None, overwrite=False):
        """
        Gets a redirect URL to download an archive for a repository. This URL expires after 1 minute. 
        Look for Location: in the response header to find the URL for the download. The :archive_format must be zip.
        You must authenticate using an access token with the repo scope to use this endpoint. GitHub Apps must have the actions:read permission to use this endpoint.

        artifact_id: The artifact ID, which you can get from the List workflow run artifacts endpoint.
        archive_format: Only zip is currently supported. Default: zip
        save_dir: Directory to save the artifact to. Default: current directory
        save_name: Name of the file to save the artifact to. By default, the artifact ID and archive format are used.
        overwrite: Whether to overwrite the file if it already exists. If overwrite=False, will stop and give a warning. Default: False
        """
        headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {self.token}',
            'X-GitHub-Api-Version': '2022-11-28'
        }

        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/artifacts/{artifact_id}/{archive_format}'
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as res:
            body = res.read()  # body is a bytes object, we need to write it to a file

        if save_name is None:
            save_name = f'{artifact_id}.{archive_format}'
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / save_name
        
        if save_path.exists():
            if overwrite:
                save_path.unlink()
            else:
                print(f'File {save_path} already exists. Skipping download.')
                return save_path

        with open(save_path, 'wb') as f:
            f.write(body)
        
        return save_path

    def extract_artifact(self, path, save_dir='./gh_artifacts', use_name_as_subdir=True, overwrite=False):
        """
        Extracts the contents of a zip file and save to a directory.

        path: Path to the zip file.
        save_dir: Directory to save the contents of the zip file to (or that will contain the subdir of use_name_as_subdir=True)
        use_name_as_subdir: Whether to use the name of the zip file as the name of the subdirectory to save the contents to. Default: True
        """
        path = Path(path)
        if path.suffix != '.zip':
            raise ValueError('Only zip files are supported.')

        if use_name_as_subdir:
            save_dir = save_dir / path.stem
        
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                filename = Path(member)

                if filename.is_dir():
                    continue
                
                if use_name_as_subdir:
                    filename = save_dir / filename
                else:
                    filename = save_dir / path.stem / filename
                
                if filename.exists():
                    if overwrite:
                        filename.unlink()
                    else:
                        print(f'File {filename} already exists. Skipping extraction.')
                        continue
                
                filename.parent.mkdir(parents=True, exist_ok=True)
                zip_ref.extract(member, save_dir)
        
        return save_dir


if __name__ == '__main__':
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description='Download the latest artifact from a GitHub repository.')
    parser.add_argument('--token', type=str, help='GitHub Personal Access Token', required=True)
    parser.add_argument('--owner', type=str, help='GitHub repository owner', required=True)
    parser.add_argument('--repo', type=str, help='GitHub repository name', required=True)
    parser.add_argument('--artifact_name', type=str, help='Name of the artifact to download')
    parser.add_argument('--save_dir', type=str, default='./gh_artifacts', help='Directory to save the artifact to')

    args = parser.parse_args()

    repo = Repository(args.token, args.owner, args.repo)
    
    # Let's get the latest artifact (always the first one, so we can use per_page=1, page=1)
    artifacts = repo.list_artifacts(per_page=1, page=1, name=args.artifact_name)

    if len(artifacts['artifacts']) == 0:
        print(f'No artifacts found with name {args.artifact_name}. Exiting.')
        exit(0)

    # Download the artifact and extract the content to the current directory, overwriting any existing files
    a = artifacts['artifacts'][0]
    artifact_path = repo.download_artifact(a['id'], overwrite=True)
    repo.extract_artifact(artifact_path, use_name_as_subdir=False, overwrite=True, save_dir=args.save_dir)
