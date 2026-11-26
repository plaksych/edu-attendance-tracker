"""Installer for a dedicated Ubuntu 24.04+ VM. Build the single-file kit with 'pack'."""
import argparse
import base64
import contextlib
import getpass
import hashlib
import http.cookiejar
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess as sp
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit
import uuid
import zipfile

HOME = Path("/etc/attendance-lgtu")
ROOT = HOME / "release"
ENV = HOME / "production.env"
APPROVAL = HOME / "approved-release.json"
PY = HOME / "venv/bin/python"
PROJECT = "attendance-prod-lgtu"
FILES = [".env.example", "docker-compose.yml", "recognition/model-manifest.json",
         *["scripts/ops/" + f for f in ("gateway.conf.template", "common.py", "manage.py",
            "roles.py", "data.py", "requirements.txt")]]


def check(value, message):
    if not value:
        raise SystemExit(message)


def run(*args, **kw):
    return sp.run([str(a) for a in args], check=True, **kw)


def pack(target, model_file=None, fetch_model=False):
    repo = Path(__file__).resolve().parents[1]
    def git(*args):
        return run("git", *args, cwd=repo, stdout=sp.PIPE).stdout
    revision = git("rev-parse", "HEAD").decode().strip()
    payload = {p: git("show", revision + ":" + p) for p in FILES}
    manifest = json.loads(payload["recognition/model-manifest.json"])
    path = model_file or repo / manifest["filename"]
    if path.is_file():
        model = path.read_bytes()
    else:
        check(fetch_model and model_file is None,
              "Нет весов: укажите --model-file /путь/yolov8n.pt или разрешите --fetch-model.")
        with urllib.request.urlopen(manifest["source"], timeout=60) as response:
            model = response.read(32 * 1024 * 1024 + 1)
    check(hashlib.sha256(model).hexdigest() == manifest["sha256"], "Model hash mismatch")
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as z:
        z.writestr("__main__.py", git("show", revision + ":scripts/lgtu_deploy.py"))
        for name, data in payload.items():
            z.writestr(name, data)
        z.writestr("model.pt", model)
        z.writestr("revision", revision)


def write_new(path, value):
    with path.open("x") as f:
        f.write(value)


def configure():
    """Take image digests from the reviewed service map, never invent a release."""
    sys.path.insert(0, str(ROOT / "scripts/ops"))
    from common import read_env
    env = read_env(ENV)
    evidence = json.loads(APPROVAL.read_text())
    check(evidence.get("revision") == (ROOT / "revision").read_text(), "Допуск для другой ревизии")
    changes = {}
    if env.get("HTTPS_BIND") == "127.0.0.1":
        changes["HTTPS_BIND"] = str(private_bind(input("Внутренний IPv4 этой ВМ: ").strip()))
    for service, key in {"db":"POSTGRES", "minio":"MINIO", "backend":"BACKEND", "frontend":"FRONTEND",
                         "recognition-worker":"RECOGNITION", "capture-manager":"CAPTURE", "gateway":"GATEWAY"}.items():
        if not env.get(key + "_IMAGE"):
            changes[key + "_IMAGE"] = evidence["images"][service]
    for name, prompt in [("APP_HOST","DNS приложения"), ("MEDIA_HOST","DNS медиа")]:
        if env[name].endswith(".invalid"):
            changes[name] = input(prompt + ": ").strip()
    if not env.get("CAMERA_ALLOWED_CIDRS"):
        changes["CAMERA_ALLOWED_CIDRS"] = input("IP камер (/32) или подсети через запятую; Enter без камер: ").strip()
    if changes:
        lines = ENV.read_text().splitlines()
        with tempfile.NamedTemporaryFile(mode="w", dir=HOME, delete=False) as f:
            for line in lines:
                k = line.partition("=")[0]
                print(k + "=" + changes[k] if k in changes else line, file=f)
        os.replace(f.name, ENV)


def prepare():
    with zipfile.ZipFile(sys.argv[0]) as z:
        for name in [*FILES, "revision", "model.pt"]:
            path = ROOT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            data = z.read(name)
            if path.exists():
                check(path.read_bytes() == data, f"Existing release differs: {name}; no upgrade attempted")
            else:
                with path.open("xb") as f:
                    f.write(data)
        # Mounted read-only inside the worker: host directory remains root-only.
        (ROOT / "model.pt").chmod(0o444)
        (ROOT / "scripts/ops/gateway.conf.template").chmod(0o444)
    if not ENV.exists():
        db = PROJECT.replace("-", "_")
        key = lambda: secrets.token_hex(24)
        values = dict(COMPOSE_PROJECT_NAME=PROJECT, DB_NAME=db, DB_ADMIN_PASSWORD=key(),
                      MINIO_BUCKET=PROJECT, MINIO_ROOT_USER="lgtu_owner", MINIO_ROOT_PASSWORD=key(),
                      MINIO_ACCESS_KEY="lgtu_runtime", MINIO_SECRET_KEY=key(),
                      MINIO_INIT_ACCESS_KEY="lgtu_init", MINIO_INIT_SECRET_KEY=key(),
                      CAMERA_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                      HTTPS_BIND="127.0.0.1", MODEL_FILE=str(ROOT / "model.pt"),
                      MODEL_SHA256=json.loads((ROOT / FILES[2]).read_text())["sha256"],
                      RECOGNITION_MODEL_VERSION="v8.3.0", TLS_CERT_FILE=str(HOME / "fullchain.pem"),
                      TLS_KEY_FILE=str(HOME / "privkey.pem"))
        for role in ("backend", "migration", "capture", "recognition"):
            values[role.upper() + "_DATABASE_URL"] = f"postgresql://{db}_{role}:{key()}@db:5432/{db}"
        lines = []
        for line in (ROOT / ".env.example").read_text().splitlines():
            k, sep, _ = line.partition("=")
            lines.append(k + "=" + values[k] if sep and k in values else line)
        write_new(ENV, "\n".join(lines) + "\n")
    if not (HOME / "instance").exists():
        write_new(HOME / "instance", str(uuid.uuid4()))
    print(f"Настройки: {ENV}. Заполните семь *_IMAGE с digest, APP_HOST, MEDIA_HOST,"
          " CAMERA_ALLOWED_CIDRS, даты семестра. Установите TLS и утверждённый approved-release.json."
          " Не пересоздавайте секреты. Сохраните защищённую резервную копию.", flush=True)


def bootstrap():
    pkgs = ["python3-venv", "ca-certificates", "openssl", "util-linux"]
    if not shutil.which("docker"):
        pkgs += ["docker.io", "docker-compose-v2"]
    elif sp.run(["docker", "compose", "version"], capture_output=True).returncode:
        ce = sp.run(["dpkg-query", "-W", "-f=${db:Status-Status}", "docker-ce-cli"], capture_output=True)
        pkgs.append("docker-compose-plugin" if ce.stdout == b"installed" else "docker-compose-v2")
    run("apt-get", "update")
    run("apt-get", "--no-remove", "install", "-y", *pkgs)
    run("systemctl", "enable", "--now", "docker")
    run("docker", "compose", "version")
    run(sys.executable, "-m", "venv", PY.parents[1])
    wheels = HOME / "wheels"
    run(PY, "-m", "pip", "install", *(["--no-index", "--find-links", wheels] if wheels.is_dir() else []),
        "-r", ROOT / "scripts/ops/requirements.txt")


def networks(env):
    nets = [ipaddress.ip_network(v.strip()) for v in env["CAMERA_ALLOWED_CIDRS"].split(",") if v.strip()]
    private = [ipaddress.ip_network(x) for x in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    check(all(n.version == 4 and any(n.subnet_of(p) for p in private) for n in nets),
          "Укажите только выделенные частные подсети камер (или /32)")
    return nets


def private_bind(value):
    addr = ipaddress.IPv4Address(value)
    check(any(addr in ipaddress.ip_network(n) for n in ("10.0.0.0/8","172.16.0.0/12","192.168.0.0/16")),
          "Укажите внутренний IPv4 интерфейса ВМ, не публичный и не loopback")
    return addr


def setup_ops():
    sys.path.insert(0, str(ROOT / "scripts/ops"))
    import common
    env = common.read_env(ENV)
    common.validate_env(env)
    check(env["COMPOSE_PROJECT_NAME"] == PROJECT, "Неверный проект")
    private_bind(env["HTTPS_BIND"])
    networks(env)
    ctx = common.compose_environment(env)
    # Always operate on the local daemon, regardless of the user's Docker context.
    def dc(*args, **kw):
        return run("docker", "--host", "unix:///var/run/docker.sock", *common.compose_args(env, ENV)[1:],
                   "--profile", "camera", "--profile", "ops", *args, env=ctx, **kw)
    return env, dc


def inspect_release(env, dc):
    import common
    from roles import role_config
    role_config(env)
    cfg = json.loads(dc("config", "--format", "json", stdout=sp.PIPE).stdout)
    common.validate_config(cfg)
    rec = json.loads(APPROVAL.read_text())
    images = {k: v["image"] for k, v in cfg["services"].items()}
    check(rec.get("revision") == (ROOT / "revision").read_text() and rec.get("images") == images
          and rec.get("schema_compatible") is True and all(rec.get(k) for k in
          ("reviewer", "ci_run", "backup_snapshot", "restore_evidence")), "Нет согласованного допуска для этих образов/SHA")
    check({socket.gethostbyname(env[k]) for k in ("APP_HOST", "MEDIA_HOST")} == {env["HTTPS_BIND"]}, "Проверьте внутренний DNS")
    with socket.socket() as probe:
        probe.bind((env["HTTPS_BIND"], 0))
    cert, key = (Path(env[k]) for k in ("TLS_CERT_FILE", "TLS_KEY_FILE"))
    check(cert.is_file() and key.is_file(), "Нет TLS сертификата или ключа")
    for host in (env["APP_HOST"], env["MEDIA_HOST"]):
        run("openssl", "verify", "-purpose", "sslserver", "-verify_hostname", host,
            "-untrusted", cert, cert, stdout=sp.PIPE)
    check(run("openssl", "x509", "-in", cert, "-pubkey", "-noout", stdout=sp.PIPE).stdout ==
          run("openssl", "pkey", "-in", key, "-pubout", stdout=sp.PIPE).stdout, "Ключ не соответствует сертификату")
    # Gateway runs as uid 101. Do not relax permissions on the supplied key.
    check(key.stat().st_mode & 7 == 0, "TLS key readable by others")
    model = Path(env["MODEL_FILE"])
    check(hashlib.sha256(model.read_bytes()).hexdigest() == env["MODEL_SHA256"] ==
          json.loads((ROOT / FILES[2]).read_text())["sha256"], "Неверные веса модели")
    return cfg


def in_namespace(dc, service, action):
    cid = dc("ps", "-q", service, stdout=sp.PIPE).stdout.decode().strip()
    pid = run("docker", "inspect", "-f", "{{.State.Pid}}", cid, stdout=sp.PIPE).stdout.decode().strip()
    check(pid.isdigit() and int(pid) > 1, "Контейнер не запущен")
    run("nsenter", "-t", pid, "-n", PY, Path(sys.argv[0]).resolve(), action)


def db_setup(env, grants):
    import psycopg2
    from roles import initialize, apply_grants
    from data import provision_marker, identity
    with contextlib.closing(psycopg2.connect(host="127.0.0.1", user=env["DB_ADMIN_USER"], dbname=env["DB_NAME"],
                           password=env["DB_ADMIN_PASSWORD"], connect_timeout=5)) as conn:
        ident = (HOME / "instance").read_text()
        with conn, conn.cursor() as c:
            c.execute("SELECT to_regnamespace('ops_control')")
            if c.fetchone()[0] is None:
                check(not grants, "Нет метки базы")
                provision_marker(conn, dict(PGDATABASE=env["DB_NAME"], OPS_MODE="production",
                                           OPS_NAMESPACE=PROJECT, OPS_INSTANCE_ID=ident))
            check(identity(conn) == (env["DB_NAME"], ("production", PROJECT, ident)), "Чужая база")
            c.execute("SELECT to_regclass('public.alembic_version')")
            migrated = c.fetchone()[0] is not None
        if grants:
            apply_grants(conn, env)
        elif not migrated:
            initialize(conn, env)


def storage(env):
    from minio import MinioAdmin
    from minio.credentials import StaticProvider
    admin = MinioAdmin("127.0.0.1:9000", StaticProvider(env["MINIO_ROOT_USER"], env["MINIO_ROOT_PASSWORD"]), secure=False)
    bucket = "arn:aws:s3:::" + env["MINIO_BUCKET"]
    for _ in range(40):
        try:
            admin.info()
            break
        except Exception:
            time.sleep(1)
    for prefix, name, rights in [("MINIO_INIT_", "lgtu-bucket-init",
            ["s3:CreateBucket", "s3:GetBucketPolicy", "s3:GetLifecycleConfiguration", "s3:PutLifecycleConfiguration"]),
            ("MINIO_", "lgtu-media", [])]:
        statements = [dict(Effect="Allow", Action=["s3:GetBucketLocation", "s3:ListBucket", *rights], Resource=[bucket])]
        if not rights:
            statements.append(dict(Effect="Allow", Action=["s3:GetObject", "s3:PutObject", "s3:DeleteObject",
                "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"], Resource=[bucket + "/*"]))
        with tempfile.NamedTemporaryFile(mode="w") as f:
            json.dump(dict(Version="2012-10-17", Statement=statements), f)
            f.flush()
            admin.policy_add(name, f.name)
        user = env[prefix + "ACCESS_KEY"]
        admin.user_add(user, env[prefix + "SECRET_KEY"])
        admin.policy_set(name, user=user)


def install(env, dc):
    cfg = inspect_release(env, dc)
    check(not (HOME / "installed").exists(), "Уже установлено. Используйте start или doctor.")
    root = Path(run("docker", "info", "-f", "{{.DockerRootDir}}", stdout=sp.PIPE).stdout.decode().strip())
    check(shutil.disk_usage(root).free >= 40 * 1024**3, "Необходимо не менее 40 ГиБ свободного места Docker")
    for ref in sorted({s["image"] for s in cfg["services"].values()}):
        if sp.run(["docker", "image", "inspect", ref], stdout=sp.DEVNULL, stderr=sp.DEVNULL).returncode:
            run("docker", "pull", ref)
    tag = (HOME / "instance").read_text()
    for key, uid in [("pgdata", 999), ("miniodata", 1000)]:
        name = cfg["volumes"][key]["name"]
        if sp.run(["docker", "volume", "inspect", name], stdout=sp.DEVNULL, stderr=sp.DEVNULL).returncode:
            run("docker", "volume", "create", "--label", "attendance.instance=" + tag,
                "--label", "com.docker.compose.project=" + PROJECT, "--label", "com.docker.compose.volume=" + key, name)
        vol = json.loads(run("docker", "volume", "inspect", name, stdout=sp.PIPE).stdout)[0]
        check((vol["Labels"] or {}).get("attendance.instance") == tag and vol["Driver"] == "local"
              and not vol["Options"], "Неизвестный том; остановка без изменения данных")
        os.chown(vol["Mountpoint"], uid, uid)
    # Dedicated root-only directory isolates the bind source from other host users.
    key = Path(env["TLS_KEY_FILE"])
    check(key.parent == HOME and not key.is_symlink(), "Используйте отдельную копию ключа в /etc/attendance-lgtu")
    cert = Path(env["TLS_CERT_FILE"])
    check(cert.parent == HOME and not cert.is_symlink(), "Разместите копию fullchain.pem в каталоге установки")
    cert.chmod(0o444)
    os.chown(key, 0, 101)
    key.chmod(0o640)
    dc("up", "-d", "--wait", "--wait-timeout", "120", "--no-build", "db", "minio")
    in_namespace(dc, "db", "_roles")
    in_namespace(dc, "minio", "_storage")
    for job in ("storage-init", "migrate"):
        dc("run", "--rm", "--no-deps", "-T", job)
    in_namespace(dc, "db", "_grants")
    from manage import SERVICES
    dc("up", "-d", "--no-build", "--wait", "--wait-timeout", "180", *SERVICES,
       *(["capture-manager"] if networks(env) else []))
    health(env)
    write_new(HOME / "installed", (ROOT / "revision").read_text())
    print("Службы запущены. Автостарт: docker.service + restart: unless-stopped.")
    dc("exec", "backend", "python", "-m", "app.admin", input("Имя первого администратора: ").strip())


def health(env):
    from manage import smoke
    for i in range(20):
        try:
            smoke(env)
            return
        except (ValueError, OSError):
            if i == 19:
                raise
            time.sleep(2)


def camera(env, dc, debug):
    addr = getpass.getpass("RTSP URL (скрытый ввод): ")
    p = urlsplit(addr)
    check(p.scheme == "rtsp" and not p.fragment and any(ipaddress.ip_address(p.hostname) in n for n in networks(env)),
          "IP не входит в разрешённую подсеть камер")
    _ = p.port
    inspect_release(env, dc)
    dc("up", "-d", "--no-deps", "--no-build", "--pull", "never", "--wait", "backend", "capture-manager")
    # A single explicitly supplied camera. Never discover or scan the campus network.
    snap = """import sys,subprocess
from cryptography.fernet import Fernet
from app.config import settings
from app.camera_security import camera_url
url=camera_url('encrypted:'+Fernet(settings.camera_encryption_key.encode()).encrypt(sys.stdin.buffer.read()).decode(),settings)
r=subprocess.run(['ffmpeg','-nostdin','-v','error','-rtsp_transport','tcp','-protocol_whitelist','tcp,rtp,rtsp','-i',url,'-frames:v','1','-vf','scale=1920:1080:force_original_aspect_ratio=decrease','-f','image2pipe','-vcodec','mjpeg','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=20)
sys.stdout.buffer.write(r.stdout);sys.exit(r.returncode)
"""
    data = dc("exec", "-T", "capture-manager", "python", "-c", snap, input=addr.encode(),
              stdout=sp.PIPE, stderr=sp.DEVNULL, timeout=30).stdout
    check(data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"), "Не удалось получить JPEG")
    dest = HOME / "last-camera.jpg"
    dest.write_bytes(data)
    print(f"RTSP/TCP: получен кадр {dest} (доступ только root).")
    if debug:
        return
    with login(env) as call:
        room = input("Аудитория: ").strip()
        name = input("Уникальное имя камеры: ").strip()
        check(room and name, "Нужны аудитория и имя")
        rooms = [r for r in call("/classrooms") if r["number"] == room]
        check(not rooms or not rooms[0]["cameras"], "У аудитории уже есть камеры; используйте интерфейс для изменения набора")
        check(not any(c["name"] == name for c in call("/cameras")), "Имя занято; существующая камера не изменена")
        r = rooms[0] if rooms else call("/classrooms", dict(number=room))
        cam = call("/cameras", dict(name=name, rtsp_url=addr, capture_group=env.get("CAPTURE_GROUP", "default")))
        print(f"Создана камера ID {cam['id']}.")
        call(f"/classrooms/{r['id']}/cameras", [dict(camera_id=cam["id"], role="primary")], "PUT")
        print("Камера привязана. Для автоматических замеров загрузите расписание этой аудитории.")


@contextlib.contextmanager
def login(env):
    api = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                     urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = f"https://{env['APP_HOST']}:{env.get('HTTPS_PORT','8443')}/api/v1"
    headers = {"Content-Type": "application/json"}
    def call(path, payload=None, method=None, extra=None):
        data = payload if isinstance(payload, bytes) or payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(base + path, data, headers={**headers, **(extra or {})}, method=method)
        with api.open(req, timeout=30) as res:
            return json.loads(res.read() or b"null")
    session = call("/auth/login", dict(username=input("Администратор приложения: "), password=getpass.getpass()))
    headers["X-CSRF-Token"] = session["csrf_token"]
    try:
        yield call
    finally:
        call("/auth/logout", {}, "POST")


def calibrate(env, photo, reference):
    check(reference is not None and 0 <= reference <= 1000, "Нужно число видимых людей: --count N (0–1000)")
    check(photo.stat().st_size <= 20 * 1024**2, "Фото больше 20 МиБ")
    data = photo.read_bytes()
    ext = "png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "jpeg"
    check(ext == "png" or data.startswith(b"\xff\xd8"), "Нужен JPEG или PNG")
    counts = {}
    with login(env) as call:
        for threshold in (0.2, 0.35, 0.5):
            boundary = secrets.token_hex(20)
            parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                     for k, v in dict(confidence_threshold=threshold, reference_people_count=reference,
                                      label="camera-calibration").items()]
            parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="sample.{ext}"\r\nContent-Type: image/{ext}\r\n\r\n'.encode(),
                      data, f'\r\n--{boundary}--\r\n'.encode()]
            job = call("/recognition/uploads", b"".join(parts), "POST", {
                "Content-Type": "multipart/form-data; boundary=" + boundary,
                "Idempotency-Key": str(uuid.uuid4())})
            path = f"/recognition/uploads/{job['id']}"
            for _ in range(180):
                state = call(path)["job"]
                check(state["status"] != "failed", f"Ошибка распознавания: материал {job['id']}")
                if state["result"]:
                    break
                time.sleep(2)
            else:
                raise SystemExit(f"Таймаут очереди; проверьте материал {job['id']}")
            n = counts[threshold] = state["result"]["people_count"]
            print(f"Порог {threshold}: найдено {n}, отклонение {n-reference:+d}, материал {job['id']}", flush=True)
    best = min(counts, key=lambda t: (abs(counts[t]-reference), abs(float(t)-0.35)))
    print("Порог для проверки на других кадрах:", best, "(не применён глобально).")


def main():
    parser = argparse.ArgumentParser(description="ЛГТУ: установка, запуск и диагностика на самой ВМ",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog="""На выделенной ВМ с sudo и systemd:
  sudo python3 lgtu-deploy.pyz prepare       создать /etc/attendance-lgtu и секреты
  sudo python3 lgtu-deploy.pyz install       первый запуск: IAM, БД, миграции, службы, администратор
  sudo python3 lgtu-deploy.pyz camera        проверить RTSP и добавить камеру в пустую аудиторию
  sudo python3 lgtu-deploy.pyz debug         получить контрольный JPEG без регистрации камеры
  sudo python3 lgtu-deploy.pyz calibrate --count 15   сравнить 3 порога по последнему JPEG
  sudo python3 lgtu-deploy.pyz doctor        проверить HTTPS, готовность API и закрытый доступ
  sudo python3 lgtu-deploy.pyz start         повторный запуск без миграций и смены паролей

Перед install: согласованный approved-release.json из регламента проекта, fullchain.pem и
privkey.pem в /etc/attendance-lgtu; внутренний УЦ должен быть доверенным. Имена приложения и
медиа указывают на внутренний IPv4 ВМ. ACL для TCP 8443 согласовать с ИТ (либо использовать
SSH-туннель с теми же DNS-именами). SSH и правила межсетевого экрана скрипт не меняет.
Нужны доступ к apt и источнику Python-пакетов (или локальные зеркала, wheels/), 7 образов
с утверждёнными digest локально или в доступном registry. Без них установка остановится.
Пароли камер вводятся без эха. Диагностический JPEG сохраняется только на ВМ.
Калибровка создаёт 3 материала в закрытом журнале сервера; можно указать --photo FILE.
Число --count задаётся по ручной разметке. Глобальные параметры камер не перезаписываются.""")
    parser.add_argument("action", choices=["pack","prepare","install","start","status","doctor","admin","camera","debug","calibrate",
                                            "_roles","_storage","_grants"])
    parser.add_argument("--output", default="lgtu-deploy.pyz")
    parser.add_argument("--model-file", type=Path, help="Файл проверенных весов для pack")
    parser.add_argument("--fetch-model", action="store_true", help="Для pack: загрузить веса по manifest, если их нет")
    parser.add_argument("--photo", type=Path, default=HOME / "last-camera.jpg")
    parser.add_argument("--count", type=int)
    args = parser.parse_args()
    if args.action == "pack":
        return pack(args.output, args.model_file, args.fetch_model)
    check(sys.platform == "linux" and os.geteuid() == 0, "Запустите через sudo на Ubuntu Server")
    check(sys.version_info >= (3,11), "Нужен Python 3.11+ (Ubuntu 24.04 LTS рекомендуется)")
    os.umask(0o077)
    for k in list(os.environ):
        if k.startswith(("COMPOSE_", "DOCKER_")):
            del os.environ[k]
    os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    os.environ["NO_PROXY"] = "*"
    HOME.mkdir(mode=0o700, exist_ok=True)
    check(not HOME.is_symlink() and HOME.stat().st_uid == 0 and not HOME.stat().st_mode & 0o077, "Небезопасный каталог настроек")
    if args.action in ("prepare","install"):
        prepare()
    if args.action == "prepare":
        return
    if args.action == "install":
        check('ID=ubuntu' in Path("/etc/os-release").read_text().splitlines(), "Нужна Ubuntu Server")
        check(APPROVAL.is_file(), f"Сначала разместите согласованный допуск: {APPROVAL}")
        if Path(sys.executable) != PY:
            configure()
        if not (HOME / "ops-ready").exists():
            bootstrap()
            write_new(HOME / "ops-ready", "1")
        run("systemctl", "enable", "--now", "docker")
    if Path(sys.executable) != PY:
        check(PY.exists(), "Сначала выполните install")
        os.execv(str(PY), [str(PY), str(Path(sys.argv[0]).resolve()), *sys.argv[1:]])
    env, dc = setup_ops()
    a = args.action
    if a in ("_roles","_grants"):
        return db_setup(env, a == "_grants")
    if a == "_storage":
        return storage(env)
    import fcntl
    with (HOME / "operation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if a == "install":
            return install(env, dc)
        if a == "status":
            return dc("ps", "-a")
        if a == "doctor":
            dc("ps", "-a")
            return health(env)
        if a == "admin":
            return dc("exec", "backend", "python", "-m", "app.admin", input("Имя администратора: ").strip())
        check((HOME / "installed").is_file(), "Установка не завершена")
        if a == "start":
            from manage import SERVICES
            dc("start", "db", "minio", *SERVICES, *(["capture-manager"] if networks(env) else []))
            return health(env)
        if a in ("camera","debug"):
            return camera(env, dc, a == "debug")
        return calibrate(env, args.photo, args.count)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        # Exceptions can contain credentials, RTSP URLs and Compose arguments.
        sys.exit(f"Операция остановлена: {type(exc).__name__}. Проверьте настройки и статус служб.")
