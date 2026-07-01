import base64
import datetime as dt
import io
import mimetypes
import os
import posixpath
import shutil
import urllib.parse
import zipfile
from functools import wraps
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from flask import Flask, Response, abort, jsonify, redirect, render_template_string, request, send_file, url_for


app = Flask(__name__)

# Config via environment variables.
DATA_ROOT = Path(os.environ.get("WEBDAV_ROOT", "./data")).resolve()
AUTH_USER = os.environ.get("WEBDAV_USERNAME", "admin")
AUTH_PASS = os.environ.get("WEBDAV_PASSWORD", "admin")

DATA_ROOT.mkdir(parents=True, exist_ok=True)


INDEX_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>Flask WebDAV</title>
	<style>
		:root {
			--bg: #f7f4ea;
			--panel: #ffffffcc;
			--ink: #172121;
			--ink-soft: #4a5759;
			--accent: #5b8e7d;
			--accent-2: #bc4b51;
			--line: #d6d2c4;
		}
		* { box-sizing: border-box; }
		body {
			margin: 0;
			min-height: 100vh;
			font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
			color: var(--ink);
			background:
				radial-gradient(circle at 10% -10%, #f9d8b444 0, transparent 40%),
				radial-gradient(circle at 90% 0%, #86a59c44 0, transparent 35%),
				var(--bg);
			padding: 1.2rem;
		}
		.wrap {
			max-width: 980px;
			margin: 0 auto;
			background: var(--panel);
			border: 1px solid var(--line);
			border-radius: 16px;
			backdrop-filter: blur(6px);
			box-shadow: 0 14px 50px #00000017;
			overflow: hidden;
		}
		header {
			background: linear-gradient(110deg, #5b8e7d, #3d6b6f);
			color: #fff;
			padding: 1.2rem;
		}
		h1 {
			margin: 0;
			font-size: clamp(1.25rem, 2.8vw, 2rem);
			letter-spacing: 0.02em;
		}
		.sub {
			margin-top: 0.4rem;
			opacity: 0.92;
			font-size: 0.95rem;
		}
		.grid {
			display: grid;
			grid-template-columns: 1fr;
			gap: 1rem;
			padding: 1rem;
		}
		@media (min-width: 900px) {
			.grid {
				grid-template-columns: 2fr 1fr;
			}
		}
		.panel {
			border: 1px solid var(--line);
			border-radius: 12px;
			background: #fff;
			overflow: hidden;
		}
		.panel h2 {
			margin: 0;
			font-size: 1rem;
			padding: 0.8rem 1rem;
			border-bottom: 1px solid var(--line);
			background: #faf9f4;
		}
		.files {
			width: 100%;
			border-collapse: collapse;
			font-size: 0.95rem;
		}
		.files th, .files td {
			text-align: left;
			border-bottom: 1px solid #ece8dc;
			padding: 0.62rem;
			vertical-align: middle;
		}
		.files th { color: var(--ink-soft); font-weight: 600; }
		.pill {
			display: inline-block;
			padding: 0.14rem 0.5rem;
			border-radius: 999px;
			border: 1px solid #d5e4df;
			background: #f1f9f6;
			color: #285143;
			font-size: 0.8rem;
			font-weight: 700;
		}
		.form {
			padding: 0.8rem 1rem 1rem;
			border-top: 1px solid #f0ede2;
		}
		.dropzone {
			margin-top: 0.6rem;
			border: 2px dashed #89a89e;
			background: #f7fcf9;
			border-radius: 12px;
			padding: 0.85rem;
			text-align: center;
			color: #355e4f;
			font-size: 0.9rem;
			transition: background .2s ease, border-color .2s ease, transform .1s ease;
		}
		.dropzone.active {
			background: #ecf8f1;
			border-color: #3d6b6f;
			transform: translateY(-1px);
		}
		.dropzone-status {
			margin-top: 0.5rem;
			font-size: 0.82rem;
			color: #4a5759;
		}
		.folder-upload-details {
			margin-top: 0.55rem;
			border: 1px solid #dde5e1;
			border-radius: 10px;
			padding: 0.45rem 0.55rem;
			background: #fbfdfc;
		}
		.folder-upload-details summary {
			cursor: pointer;
			font-size: 0.88rem;
			font-weight: 700;
			color: #3d6b6f;
			list-style: none;
		}
		.folder-upload-details summary::-webkit-details-marker {
			display: none;
		}
		.folder-upload-details summary::before {
			content: ">";
			display: inline-block;
			margin-right: 0.4rem;
			transition: transform .16s ease;
		}
		.folder-upload-details[open] summary::before {
			transform: rotate(90deg);
		}
		.folder-upload-fields {
			margin-top: 0.5rem;
		}
		.upload-results {
			margin-top: 0.7rem;
			border: 1px solid #d8e4dd;
			background: #fbfdfc;
			border-radius: 10px;
			padding: 0.55rem 0.65rem;
			max-height: 240px;
			overflow: auto;
		}
		.upload-results .title {
			font-size: 0.82rem;
			font-weight: 700;
			color: #3b5052;
			margin-bottom: 0.35rem;
		}
		.upload-results ul {
			margin: 0;
			padding: 0;
			list-style: none;
		}
		.upload-results li {
			font-size: 0.82rem;
			padding: 0.22rem 0;
			border-bottom: 1px dashed #e8ecea;
		}
		.upload-results li:last-child {
			border-bottom: 0;
		}
		.upload-ok {
			color: #236845;
		}
		.upload-fail {
			color: #8c2f39;
		}
		.upload-pending {
			color: #4a5759;
		}
		label {
			display: block;
			margin: 0.45rem 0 0.25rem;
			color: var(--ink-soft);
			font-size: 0.86rem;
			font-weight: 600;
		}
		input[type="text"], input[type="file"] {
			width: 100%;
			padding: 0.55rem 0.65rem;
			border: 1px solid var(--line);
			border-radius: 10px;
			font-size: 0.93rem;
			background: #fff;
		}
		.btn {
			margin-top: 0.65rem;
			width: 100%;
			padding: 0.58rem 0.8rem;
			border: 0;
			border-radius: 10px;
			color: #fff;
			font-weight: 700;
			cursor: pointer;
			background: linear-gradient(120deg, #3d6b6f, #5b8e7d);
			transition: transform .12s ease, filter .15s ease;
		}
		.btn:hover { filter: brightness(1.03); }
		.btn:active { transform: translateY(1px); }
		.btn-danger { background: linear-gradient(120deg, #bc4b51, #8c2f39); }
		.small {
			color: #6a6f73;
			font-size: 0.82rem;
			margin-top: 0.6rem;
			line-height: 1.4;
		}
		a { color: #134f5c; text-decoration: none; }
		a:hover { text-decoration: underline; }
		.row-actions form { display: inline; }
	</style>
</head>
<body>
	<div class="wrap">
		<header>
			<h1>Flask WebDAV + Web UI</h1>
			<div class="sub">Current path: /{{ current_path }}</div>
			<div class="sub">WebDAV base URL: {{ webdav_base }}</div>
		</header>

		<div class="grid">
			<section class="panel">
				<h2>Files & Folders</h2>
				<table class="files">
					<thead>
						<tr>
							<th>Name</th>
							<th>Type</th>
							<th>Size</th>
							<th>Modified</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
						{% if parent_path is not none %}
							<tr>
								<td><a href="{{ url_for('ui_list', subpath=parent_path) }}">.. (parent)</a></td>
								<td><span class="pill">dir</span></td>
								<td>-</td>
								<td>-</td>
								<td>-</td>
							</tr>
						{% endif %}
						{% for e in entries %}
							<tr>
								{% if e.is_dir %}
									<td><a href="{{ url_for('ui_list', subpath=e.rel_path) }}">{{ e.name }}</a></td>
									<td><span class="pill">dir</span></td>
									<td>-</td>
								{% else %}
									<td>{{ e.name }}</td>
									<td>file</td>
									<td>{{ e.size }}</td>
								{% endif %}
								<td>{{ e.mtime }}</td>
								<td class="row-actions">
									{% if e.is_dir %}
										<a href="{{ url_for('ui_download_folder', folder_path=e.rel_path) }}">download zip</a>
									{% else %}
										<a href="{{ url_for('ui_download', file_path=e.rel_path) }}">download</a>
									{% endif %}
									<form action="{{ url_for('ui_delete') }}" method="post">
										<input type="hidden" name="target" value="{{ e.rel_path }}">
										<input type="hidden" name="current_path" value="{{ current_path }}">
										<button class="btn btn-danger" style="width:auto;padding:.35rem .55rem;margin:0 0 0 .5rem;">delete</button>
									</form>
								</td>
							</tr>
						{% endfor %}
					</tbody>
				</table>
			</section>

			<aside class="panel">
				<h2>Operations</h2>
				<form class="form" id="uploadForm" action="{{ url_for('ui_upload') }}" method="post" enctype="multipart/form-data">
					<input type="hidden" name="current_path" value="{{ current_path }}">
					<label for="upload_file">Upload files (multiple)</label>
					<input id="upload_file" type="file" name="files" multiple>
					<details class="folder-upload-details">
						<summary>Upload folder</summary>
						<div class="folder-upload-fields">
							<label for="upload_folder">Choose folder files</label>
							<input id="upload_folder" type="file" name="folder_files" webkitdirectory directory multiple>
						</div>
					</details>
					<div id="dropzone" class="dropzone">
						Drag and drop files or folders here
						<div class="dropzone-status" id="dropzoneStatus">No dropped items yet</div>
					</div>
					<div class="upload-results" id="uploadResults" style="display:none;">
						<div class="title">Upload Status</div>
						<ul id="uploadResultsList"></ul>
					</div>
					<button class="btn" type="submit">Upload Selection</button>
				</form>

				<form class="form" action="{{ url_for('ui_mkdir') }}" method="post">
					<input type="hidden" name="current_path" value="{{ current_path }}">
					<label for="folder_name">Create folder</label>
					<input id="folder_name" type="text" name="folder_name" placeholder="example-folder" required>
					<button class="btn" type="submit">Create Folder</button>
				</form>

				<div class="form small">
					WebDAV clients can connect to the same host and use the root path. Supported methods include PROPFIND, PUT, MKCOL, DELETE, COPY and MOVE.
				</div>
			</aside>
		</div>
	</div>
	<script>
		(function () {
			const form = document.getElementById("uploadForm");
			const dropzone = document.getElementById("dropzone");
			const status = document.getElementById("dropzoneStatus");
			const fileInput = document.getElementById("upload_file");
 			const folderInput = document.getElementById("upload_folder");
			const resultsBox = document.getElementById("uploadResults");
			const resultsList = document.getElementById("uploadResultsList");

			if (!form || !dropzone || !status || !fileInput || !folderInput || !resultsBox || !resultsList) {
				return;
			}

			const droppedFiles = [];

			function setStatus() {
				if (droppedFiles.length === 0) {
					status.textContent = "No dropped items yet";
					return;
				}
				status.textContent = "Dropped " + droppedFiles.length + " item(s). They will be uploaded when you submit.";
			}

			function showResults(items, summary, hasFailures) {
				resultsList.innerHTML = "";
				resultsBox.style.display = "block";

				const summaryLine = document.createElement("li");
				summaryLine.className = hasFailures ? "upload-fail" : "upload-ok";
				summaryLine.textContent = summary;
				resultsList.appendChild(summaryLine);

				for (const item of items) {
					const row = document.createElement("li");
					row.className = item.ok ? "upload-ok" : "upload-fail";
					const icon = item.ok ? "OK" : "FAIL";
					row.textContent = "[" + icon + "] " + item.source_name + " -> " + item.saved_as + " : " + item.message;
					resultsList.appendChild(row);
				}
			}

			function showPendingSummary() {
				const pickerCount = (fileInput.files ? fileInput.files.length : 0) + (folderInput.files ? folderInput.files.length : 0);
				const total = pickerCount + droppedFiles.length;
				if (!total) {
					resultsBox.style.display = "none";
					return false;
				}
				resultsBox.style.display = "block";
				resultsList.innerHTML = "";
				const line = document.createElement("li");
				line.className = "upload-pending";
				line.textContent = "Uploading " + total + " item(s)...";
				resultsList.appendChild(line);
				return true;
			}

			function addFile(file, relativePath) {
				if (relativePath) {
					Object.defineProperty(file, "webkitRelativePath", {
						value: relativePath,
						configurable: true
					});
				}
				droppedFiles.push(file);
			}

			async function traverseEntry(entry, parentPath) {
				if (entry.isFile) {
					await new Promise((resolve) => {
						entry.file((file) => {
							const rel = parentPath ? parentPath + "/" + file.name : file.name;
							addFile(file, rel);
							resolve();
						});
					});
					return;
				}

				if (!entry.isDirectory) {
					return;
				}

				const dirReader = entry.createReader();
				const dirPath = parentPath ? parentPath + "/" + entry.name : entry.name;
				while (true) {
					const entries = await new Promise((resolve) => dirReader.readEntries(resolve));
					if (!entries.length) {
						break;
					}
					for (const child of entries) {
						await traverseEntry(child, dirPath);
					}
				}
			}

			async function ingestDrop(dataTransfer) {
				const items = Array.from(dataTransfer.items || []);
				if (!items.length) {
					for (const f of Array.from(dataTransfer.files || [])) {
						addFile(f, "");
					}
					setStatus();
					return;
				}

				for (const item of items) {
					if (item.kind !== "file") {
						continue;
					}
					const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
					if (entry) {
						await traverseEntry(entry, "");
					} else {
						const file = item.getAsFile();
						if (file) {
							addFile(file, "");
						}
					}
				}
				setStatus();
			}

			["dragenter", "dragover"].forEach((eventName) => {
				dropzone.addEventListener(eventName, (e) => {
					e.preventDefault();
					e.stopPropagation();
					dropzone.classList.add("active");
				});
			});

			["dragleave", "drop"].forEach((eventName) => {
				dropzone.addEventListener(eventName, (e) => {
					e.preventDefault();
					e.stopPropagation();
					dropzone.classList.remove("active");
				});
			});

			dropzone.addEventListener("drop", async (e) => {
				await ingestDrop(e.dataTransfer);
			});

			form.addEventListener("submit", (e) => {
				e.preventDefault();
				if (!showPendingSummary()) {
					return;
				}
				const fd = new FormData(form);
				for (const file of droppedFiles) {
					if (file.webkitRelativePath) {
						fd.append("folder_files", file, file.webkitRelativePath);
					} else {
						fd.append("files", file, file.name);
					}
				}

				fetch(form.action, {
					method: "POST",
					body: fd,
					credentials: "same-origin",
					headers: {
						"X-Requested-With": "XMLHttpRequest",
						"Accept": "application/json"
					}
				}).then(async (resp) => {
					let data = null;
					try {
						data = await resp.json();
					} catch (err) {
						showResults([], "Upload failed: server returned non-JSON response.", true);
						return;
					}

					const results = Array.isArray(data.results) ? data.results : [];
					const summary = data.summary || "Upload completed.";
					const failCount = Number(data.failed || 0);
					showResults(results, summary, failCount > 0 || !resp.ok);

					if (resp.ok && failCount === 0) {
						setTimeout(() => {
							window.location.reload();
						}, 800);
					}
				}).catch(() => {
					showResults([], "Upload failed: network or server error.", true);
				});
			});

			fileInput.addEventListener("change", () => {
				if (fileInput.files && fileInput.files.length > 0) {
					status.textContent = "Selected " + fileInput.files.length + " file(s) from file picker.";
				}
			});

			folderInput.addEventListener("change", () => {
				if (folderInput.files && folderInput.files.length > 0) {
					status.textContent = "Selected folder content with " + folderInput.files.length + " file(s).";
				}
			});
		})();
	</script>
</body>
</html>
"""


def _auth_failed() -> Response:
		response = Response("Authentication required", status=401)
		response.headers["WWW-Authenticate"] = 'Basic realm="Flask-WebDAV"'
		return response


def _check_basic_auth() -> bool:
		header = request.headers.get("Authorization", "")
		if not header.startswith("Basic "):
				return False
		token = header.split(" ", 1)[1].strip()
		try:
				decoded = base64.b64decode(token).decode("utf-8")
		except Exception:
				return False
		if ":" not in decoded:
				return False
		username, password = decoded.split(":", 1)
		return username == AUTH_USER and password == AUTH_PASS


def requires_auth(fn):
		@wraps(fn)
		def wrapper(*args, **kwargs):
				if not _check_basic_auth():
						return _auth_failed()
				return fn(*args, **kwargs)

		return wrapper


def _to_safe_rel_path(raw_path: str) -> str:
		clean = urllib.parse.unquote(raw_path or "")
		clean = clean.lstrip("/")
		normalized = posixpath.normpath(clean)
		if normalized in (".", ""):
				return ""
		if normalized.startswith("../") or normalized == "..":
				abort(400, "Invalid path")
		return normalized


def _full_path(rel_path: str) -> Path:
		candidate = (DATA_ROOT / rel_path).resolve()
		try:
				candidate.relative_to(DATA_ROOT)
		except ValueError:
				abort(403, "Path escapes root")
		return candidate


def _format_http_date(ts: float) -> str:
		return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _iso_utc(ts: float) -> str:
		return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _entry_payload(path: Path, rel_path: str):
		stat = path.stat()
		return {
				"name": path.name,
				"rel_path": rel_path,
				"is_dir": path.is_dir(),
				"size": stat.st_size,
				"mtime": dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
		}


def _dav_href(rel_path: str, is_dir: bool) -> str:
		encoded = urllib.parse.quote(rel_path)
		href = "/" + encoded if encoded else "/"
		if is_dir and not href.endswith("/"):
				href += "/"
		return href


def _add_prop_response(multistatus: Element, rel_path: str, full_path: Path) -> None:
		response = SubElement(multistatus, "{DAV:}response")
		href = SubElement(response, "{DAV:}href")
		href.text = _dav_href(rel_path, full_path.is_dir())

		propstat = SubElement(response, "{DAV:}propstat")
		prop = SubElement(propstat, "{DAV:}prop")
		status = SubElement(propstat, "{DAV:}status")
		status.text = "HTTP/1.1 200 OK"

		st = full_path.stat()
		creation = SubElement(prop, "{DAV:}creationdate")
		creation.text = _iso_utc(st.st_ctime)

		last_modified = SubElement(prop, "{DAV:}getlastmodified")
		last_modified.text = _format_http_date(st.st_mtime)

		length = SubElement(prop, "{DAV:}getcontentlength")
		length.text = "0" if full_path.is_dir() else str(st.st_size)

		ctype = SubElement(prop, "{DAV:}getcontenttype")
		guessed = mimetypes.guess_type(full_path.name)[0] if full_path.is_file() else "httpd/unix-directory"
		ctype.text = guessed or "application/octet-stream"

		resource_type = SubElement(prop, "{DAV:}resourcetype")
		if full_path.is_dir():
				SubElement(resource_type, "{DAV:}collection")


def _propfind(rel_path: str) -> Response:
		base = _full_path(rel_path)
		if not base.exists():
				return Response(status=404)

		depth = request.headers.get("Depth", "0")
		depth_is_one = depth == "1"

		multistatus = Element("{DAV:}multistatus")
		_add_prop_response(multistatus, rel_path, base)

		if depth_is_one and base.is_dir():
				for child in sorted(base.iterdir(), key=lambda p: p.name.lower()):
						child_rel = f"{rel_path}/{child.name}" if rel_path else child.name
						_add_prop_response(multistatus, child_rel, child)

		xml_body = tostring(multistatus, encoding="utf-8", xml_declaration=True)
		response = Response(xml_body, status=207, content_type="application/xml; charset=utf-8")
		return response


def _copy_recursive(src: Path, dst: Path) -> None:
		if src.is_dir():
				shutil.copytree(src, dst)
		else:
				dst.parent.mkdir(parents=True, exist_ok=True)
				shutil.copy2(src, dst)


def _delete_path(target: Path) -> None:
		if target.is_dir():
				shutil.rmtree(target)
		else:
				target.unlink()


def _zip_directory_bytes(folder: Path) -> io.BytesIO:
		buffer = io.BytesIO()
		with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
				for root, dirs, files in os.walk(folder):
						root_path = Path(root)
						rel_root = root_path.relative_to(folder)
						if not files and not dirs and rel_root != Path("."):
								zf.writestr(str(rel_root).replace("\\", "/") + "/", "")
						for name in files:
								full = root_path / name
								arcname = full.relative_to(folder)
								zf.write(full, arcname=str(arcname).replace("\\", "/"))
		buffer.seek(0)
		return buffer


def _sanitize_upload_filename(raw_name: str, preserve_tree: bool) -> str:
		name = (raw_name or "").replace("\\", "/").strip()
		if not name:
				raise ValueError("Invalid upload filename")

		if preserve_tree:
				normalized = posixpath.normpath(name.lstrip("/"))
				if normalized in ("", ".") or normalized.startswith("../") or normalized == "..":
						raise ValueError("Invalid folder upload path")
				return normalized

		base = os.path.basename(name)
		if not base:
				raise ValueError("Invalid upload filename")
		return base


def _wants_json_upload_response() -> bool:
		accept = request.headers.get("Accept", "")
		requested_with = request.headers.get("X-Requested-With", "")
		return "application/json" in accept or requested_with == "XMLHttpRequest"


def _store_uploaded_file(upload, target_dir: Path, rel_path: str, preserve_tree: bool) -> dict:
		source_name = upload.filename or "<unnamed>"
		try:
				safe_name = _sanitize_upload_filename(source_name, preserve_tree=preserve_tree)
				if preserve_tree:
						saved_rel = f"{rel_path}/{safe_name}" if rel_path else safe_name
						destination = _full_path(saved_rel)
				else:
						saved_rel = f"{rel_path}/{safe_name}" if rel_path else safe_name
						destination = target_dir / safe_name

				destination.parent.mkdir(parents=True, exist_ok=True)
				upload.save(destination)
				return {
						"ok": True,
						"source_name": source_name,
						"saved_as": saved_rel,
						"message": "uploaded",
				}
		except Exception as err:
				return {
						"ok": False,
						"source_name": source_name,
						"saved_as": "-",
						"message": str(err),
				}


@app.route("/ui/")
@app.route("/ui/<path:subpath>")
@requires_auth
def ui_list(subpath: str = ""):
		rel_path = _to_safe_rel_path(subpath)
		current = _full_path(rel_path)
		if not current.exists() or not current.is_dir():
				abort(404)

		entries = []
		for item in sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
				child_rel = f"{rel_path}/{item.name}" if rel_path else item.name
				entries.append(_entry_payload(item, child_rel))

		parent_path = None
		if rel_path:
				parent_path = posixpath.dirname(rel_path)
				if parent_path == ".":
						parent_path = ""

		return render_template_string(
				INDEX_TEMPLATE,
				current_path=rel_path,
				parent_path=parent_path,
				entries=entries,
				webdav_base=request.url_root.rstrip("/"),
		)


@app.post("/ui/upload")
@requires_auth
def ui_upload():
		rel_path = _to_safe_rel_path(request.form.get("current_path", ""))
		target_dir = _full_path(rel_path)
		if not target_dir.exists() or not target_dir.is_dir():
				abort(404)

		plain_files = [f for f in request.files.getlist("files") if f and f.filename]
		folder_files = [f for f in request.files.getlist("folder_files") if f and f.filename]
		if not plain_files and not folder_files:
				if _wants_json_upload_response():
						return jsonify({
								"ok": False,
								"uploaded": 0,
								"failed": 0,
								"summary": "No files provided",
								"results": [],
						}), 400
				abort(400, "No files provided")

		results = []
		for upload in plain_files:
				results.append(_store_uploaded_file(upload, target_dir, rel_path, preserve_tree=False))

		for upload in folder_files:
				results.append(_store_uploaded_file(upload, target_dir, rel_path, preserve_tree=True))

		uploaded = sum(1 for r in results if r["ok"])
		failed = sum(1 for r in results if not r["ok"])
		summary = f"Uploaded {uploaded} file(s), failed {failed}."

		if _wants_json_upload_response():
				status_code = 200 if failed == 0 else 207
				return jsonify({
						"ok": failed == 0,
						"uploaded": uploaded,
						"failed": failed,
						"summary": summary,
						"results": results,
				}), status_code

		return redirect(url_for("ui_list", subpath=rel_path))


@app.post("/ui/mkdir")
@requires_auth
def ui_mkdir():
		rel_path = _to_safe_rel_path(request.form.get("current_path", ""))
		folder_name = request.form.get("folder_name", "").strip()
		if not folder_name:
				abort(400, "Folder name is required")

		folder_name = os.path.basename(folder_name)
		target = _full_path(rel_path) / folder_name
		target.mkdir(parents=False, exist_ok=False)
		return redirect(url_for("ui_list", subpath=rel_path))


@app.post("/ui/delete")
@requires_auth
def ui_delete():
		target_rel = _to_safe_rel_path(request.form.get("target", ""))
		current_rel = _to_safe_rel_path(request.form.get("current_path", ""))
		target = _full_path(target_rel)
		if not target.exists():
				abort(404)
		_delete_path(target)
		return redirect(url_for("ui_list", subpath=current_rel))


@app.get("/ui/download/<path:file_path>")
@requires_auth
def ui_download(file_path: str):
		rel_path = _to_safe_rel_path(file_path)
		full = _full_path(rel_path)
		if not full.exists() or not full.is_file():
				abort(404)
		return send_file(full, as_attachment=True)


@app.get("/ui/download-folder/<path:folder_path>")
@requires_auth
def ui_download_folder(folder_path: str):
		rel_path = _to_safe_rel_path(folder_path)
		full = _full_path(rel_path)
		if not full.exists() or not full.is_dir():
				abort(404)

		archive = _zip_directory_bytes(full)
		archive_name = f"{full.name or 'folder'}.zip"
		return send_file(archive, as_attachment=True, download_name=archive_name, mimetype="application/zip")


@app.route("/", defaults={"req_path": ""}, methods=["GET", "HEAD", "OPTIONS", "PROPFIND", "MKCOL", "PUT", "DELETE", "MOVE", "COPY"])
@app.route("/<path:req_path>", methods=["GET", "HEAD", "OPTIONS", "PROPFIND", "MKCOL", "PUT", "DELETE", "MOVE", "COPY"])
@requires_auth
def webdav(req_path: str):
		rel_path = _to_safe_rel_path(req_path)
		target = _full_path(rel_path)
		method = request.method.upper()

		if method == "OPTIONS":
				response = Response(status=200)
				response.headers["DAV"] = "1,2"
				response.headers["MS-Author-Via"] = "DAV"
				response.headers["Allow"] = "OPTIONS, PROPFIND, GET, HEAD, PUT, DELETE, MKCOL, MOVE, COPY"
				return response

		if method == "PROPFIND":
				return _propfind(rel_path)

		if method == "MKCOL":
				if target.exists():
						return Response(status=405)
				if not target.parent.exists():
						return Response(status=409)
				target.mkdir(parents=False)
				return Response(status=201)

		if method == "PUT":
				target.parent.mkdir(parents=True, exist_ok=True)
				with target.open("wb") as out:
						out.write(request.get_data())
				return Response(status=201)

		if method == "DELETE":
				if not target.exists():
						return Response(status=404)
				_delete_path(target)
				return Response(status=204)

		if method in ("MOVE", "COPY"):
				destination = request.headers.get("Destination", "")
				if not destination:
						return Response(status=400)
				parsed = urllib.parse.urlparse(destination)
				dest_rel = _to_safe_rel_path(parsed.path)
				dest_path = _full_path(dest_rel)
				overwrite = request.headers.get("Overwrite", "T").upper() == "T"

				if not target.exists():
						return Response(status=404)

				if dest_path.exists():
						if not overwrite:
								return Response(status=412)
						_delete_path(dest_path)

				if not dest_path.parent.exists():
						return Response(status=409)

				if method == "COPY":
						_copy_recursive(target, dest_path)
				else:
						shutil.move(str(target), str(dest_path))
				return Response(status=201)

		# Browser users visiting root are redirected to the UI.
		if rel_path == "" and method == "GET":
				return redirect(url_for("ui_list", subpath=""))

		if method in ("GET", "HEAD"):
				if not target.exists():
						return Response(status=404)
				if target.is_dir():
						return Response(status=200)
				return send_file(target, as_attachment=False)

		return Response(status=405)


@app.get("/healthz")
def healthz():
		return {"status": "ok", "data_root": str(DATA_ROOT)}


if __name__ == "__main__":
		host = os.environ.get("HOST", "0.0.0.0")
		port = int(os.environ.get("PORT", "5000"))
		app.run(host=host, port=port, debug=False)
