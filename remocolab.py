import apt, apt.debfile
import pathlib, stat, shutil, urllib.request, subprocess, getpass, time, tempfile
import secrets, json, re
import IPython.utils.io
import ipywidgets

# https://salsa.debian.org/apt-team/python-apt
# https://apt-team.pages.debian.net/python-apt/library/index.html
class _NoteProgress(apt.progress.base.InstallProgress, apt.progress.base.AcquireProgress, apt.progress.base.OpProgress):
  def __init__(self):
    apt.progress.base.InstallProgress.__init__(self)
    self._label = ipywidgets.Label()
    display(self._label)
    self._float_progress = ipywidgets.FloatProgress(min = 0.0, max = 1.0, layout = {'border':'1px solid #118800'})
    display(self._float_progress)

  def close(self):
    self._float_progress.close()
    self._label.close()

  def fetch(self, item):
    self._label.value = "fetch: " + item.shortdesc

  def pulse(self, owner):
    self._float_progress.value = self.current_items / self.total_items
    return True

  def status_change(self, pkg, percent, status):
    self._label.value = "%s: %s" % (pkg, status)
    self._float_progress.value = percent / 100.0

  def update(self, percent=None):
    self._float_progress.value = self.percent / 100.0
    self._label.value = self.op + ": " + self.subop

  def done(self, item=None):
    pass

class _MyApt:
  def __init__(self):
    self._progress = _NoteProgress()
    self._cache = apt.Cache(self._progress)

  def close(self):
    self._cache.close()
    self._cache = None
    self._progress.close()
    self._progress = None

  def update_upgrade(self):
    self._cache.update()
    self._cache.open(None)
    self._cache.upgrade()

  def commit(self):
    self._cache.commit(self._progress, self._progress)
    self._cache.clear()

  def installPkg(self, *args):
    for name in args:
      pkg = self._cache[name]
      if pkg.is_installed:
        print(f"{name} is already installed")
      else:
        print(f"Install {name}")
        pkg.mark_install()

  def installDebPackage(self, name):
    apt.debfile.DebPackage(name, self._cache).install()

  def deleteInstalledPkg(self, *args):
    for pkg in self._cache:
      if pkg.is_installed:
        for name in args:
          if pkg.name.startswith(name):
            #print(f"Delete {pkg.name}")
            pkg.mark_delete()

def _download(url, path):
  try:
    with urllib.request.urlopen(url) as response:
      with open(path, 'wb') as outfile:
        shutil.copyfileobj(response, outfile)
  except:
    print("Failed to download ", url)
    raise


def _setupSSHDImpl(ngrok_token, ngrok_region):
  #apt-get update
  #apt-get upgrade
  my_apt = _MyApt()
  #Following packages are useless because nvidia kernel modules are already loaded and I cannot remove or update it.
  #Uninstall them because upgrading them take long time.
  my_apt.commit()
  my_apt.update_upgrade()
  my_apt.commit()

  subprocess.run(["unminimize"], input = "y\n", check = True, universal_newlines = True)

  my_apt.installPkg("openssh-server","xfce4","xrdp")
  my_apt.commit()
  my_apt.close()

  #Reset host keys
  for i in pathlib.Path("/etc/ssh").glob("ssh_host_*_key"):
    i.unlink()
  subprocess.run(
                  ["ssh-keygen", "-A"],
                  check = True)

  #Prevent ssh session disconnection.
  with open("/etc/ssh/sshd_config", "a") as f:
    f.write("\n\nClientAliveInterval 120\n")

  msg = ""
  msg += "ECDSA key fingerprint of host:\n"
  ret = subprocess.run(
                ["ssh-keygen", "-lvf", "/etc/ssh/ssh_host_ecdsa_key.pub"],
                stdout = subprocess.PIPE,
                check = True,
                universal_newlines = True)
  msg += ret.stdout + "\n"

  _download("https://bin.equinox.io/c/4VmDzA7iaHb/ngrok-stable-linux-amd64.zip", "ngrok.zip")
  shutil.unpack_archive("ngrok.zip")
  pathlib.Path("ngrok").chmod(stat.S_IXUSR)

  root_password = "vinh123456"
  user_password = "vinh123456"
  user_name = "cnt"
  msg += "✂️"*24 + "\n"
  msg += f"root password: {root_password}\n"
  msg += f"{user_name} password: {user_password}\n"
  msg += "✂️"*24 + "\n"
  subprocess.run(["useradd", "-s", "/bin/bash", "-m", user_name])
  subprocess.run(["adduser", user_name, "sudo"], check = True)
  subprocess.run(["chpasswd"], input = f"root:{root_password}", universal_newlines = True)
  subprocess.run(["chpasswd"], input = f"{user_name}:{user_password}", universal_newlines = True)
  subprocess.run(["service", "ssh", "restart"])
  subprocess.run(["service", "xrdp", "start"])

  if not pathlib.Path('/root/.ngrok2/ngrok.yml').exists():
    subprocess.run(["./ngrok", "authtoken", ngrok_token])

  ngrok_proc = subprocess.Popen(["./ngrok", "tcp", "-region", ngrok_region, "3389"])
  time.sleep(2)
  if ngrok_proc.poll() != None:
    raise RuntimeError("Failed to run ngrok. Return code:" + str(ngrok_proc.returncode) + "\nSee runtime log for more info.")

  with urllib.request.urlopen("http://localhost:4040/api/tunnels") as response:
    url = json.load(response)['tunnels'][0]['public_url']
    m = re.match("tcp://(.+):(\d+)", url)

  hostname = m.group(1)
  port = m.group(2)

  ssh_common_options =  "-o UserKnownHostsFile=/dev/null -o VisualHostKey=yes"
  msg += "---\n"
  msg += "Command to connect to the ssh server:\n"
  msg += "✂️"*24 + "\n"
  msg += f"ssh {ssh_common_options} -p {port} {user_name}@{hostname}\n"
  msg += "✂️"*24 + "\n"
  return msg

def _setupSSHDMain(ngrok_region):
  print("---")
  print("Copy&paste your tunnel authtoken from https://dashboard.ngrok.com/auth")
  print("(You need to sign up for ngrok and login,)")
  #Set your ngrok Authtoken.
  ngrok_token = getpass.getpass()

  return (True, _setupSSHDImpl(ngrok_token, ngrok_region))

def setupSSHD(ngrok_region = "ap", check_gpu_available = False):
  s, msg = _setupSSHDMain(ngrok_region)
  print(msg)




