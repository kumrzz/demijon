# Flask WebDAV Server + Web UI

A lightweight Flask server that exposes a WebDAV-compatible endpoint and a browser UI for file upload/download.

## Features

- Basic auth for both WebDAV and browser UI
- Web UI at `/ui/` for:
  - browse folders
  - upload multiple files, modifiedtime preserved
  - upload full folders (directory tree)
  - drag-and-drop files and folders
  - per-file upload success/failure status in the operations panel
  - download files, modifiedtime preserved
  - download folders as zip
  - create folders
  - delete files/folders
  - restore prior versions of files
- Ampache access
- WebDAV methods:
  - `OPTIONS`
  - `PROPFIND` (Depth `0` and `1`)
  - `GET` / `HEAD`
  - `PUT`
  - `MKCOL`
  - `DELETE`
  - `COPY`
  - `MOVE`

## Install

```bash
python3 -m venv .pywebdavenv
source .pywebdavenv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
export WEBDAV_USERNAME=admin
export WEBDAV_PASSWORD=thisisaweakpaswordchangeitnow
export WEBDAV_ROOT=./data
python app.py
```

Server defaults:

- Host: `0.0.0.0`
- Port: `5000`
- UI: `http://localhost:5000/ui/`
- WebDAV base: `http://localhost:5000/`

## WebDAV Client Example

Use a client URL like:

`http://localhost:5000/`

with the same username/password.

## Notes

- Change default credentials before exposing this service.
- This is intended for trusted/local usage. Add TLS and stronger auth for production.
