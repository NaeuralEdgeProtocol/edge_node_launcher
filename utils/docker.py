import os
import sys
import subprocess
import platform
import base64

from pathlib import Path
from collections import OrderedDict
from time import sleep
from uuid import uuid4

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QDialog, QInputDialog, QLabel,
                             QMessageBox, QProgressBar, QSizePolicy, QTextEdit, QVBoxLayout)

from .const import *
from .docker_commands import DockerCommandHandler
from .screen_geometry import screen_geometry
from widgets.dialogs.DockerCheckDialog import DockerCheckDialog

DOCKER_CHECK_TIMEOUT_SECONDS = 10
DOCKER_CLEANUP_TIMEOUT_SECONDS = 30
DOCKER_STOP_TIMEOUT_SECONDS = 45
DOCKER_LAUNCH_TIMEOUT_SECONDS = 120
GPU_CHECK_TIMEOUT_SECONDS = 5
WINDOWS_CREATE_NO_WINDOW = 0x08000000


def check_output_no_window(command, timeout: int):
  kwargs = {
    "stderr": subprocess.STDOUT,
    "universal_newlines": True,
    "timeout": timeout,
  }
  if os.name == 'nt':
    kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", WINDOWS_CREATE_NO_WINDOW)
  return subprocess.check_output(command, **kwargs)


def get_user_folder():
  """
  Returns the user folder.
  """
  return Path.home() / HOME_SUBFOLDER

class DockerPullThread(QThread):
  progress_update = pyqtSignal(str, int)
  pull_finished = pyqtSignal(bool)

  def __init__(self, docker_pull_command):
    super().__init__()
    self.docker_pull_command = docker_pull_command
    self.total_layers = 0
    self.pulled_layers = 0    
    return


  def run(self):
    try:
      docker_pull_command = self.docker_pull_command    
      if os.name == 'nt':
        process = subprocess.Popen(docker_pull_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW)
      else:
        process = subprocess.Popen(docker_pull_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

      for line in iter(process.stdout.readline, ''):
        self.parse_output(line)
        self.progress_update.emit(line.strip(), self.calculate_progress())
      
      process.stdout.close()
      process.wait()

      if process.returncode == 0:
        self.pull_finished.emit(True)
      else:
        self.pull_finished.emit(False)

    except subprocess.CalledProcessError:
      self.pull_finished.emit(False)
    return


  def parse_output(self, line):    
    DONE = [
      'Image is up to date',
      'Pull complete',
      'Already exists',
    ]
    START = [
      'Already exists',
      'Pulling fs layer',
      'Image is up to date',
    ]
    for d in DONE:
      if d in line:
        self.pulled_layers += 1
    for s in START:
      if s in line:
        self.total_layers += 1
    return


  def calculate_progress(self):
    if self.total_layers == 0:
      return 0
    return int((self.pulled_layers / self.total_layers) * 100)
  


class ProgressBarWindow(QDialog):
  def __init__(self, message, icon_object, sender):
    super().__init__()
    self.sender = sender
    self.setWindowTitle("Progress")
    self.setObjectName("legacyDockerPullProgressDialog")
    self.setAccessibleName("Docker pull progress")
    self.setWindowIcon(icon_object)
    self.setWindowModality(Qt.ApplicationModal)
    self.resize(600, 400)
    self.setMinimumSize(560, 360)
    layout = QVBoxLayout()
    layout.setContentsMargins(18, 18, 18, 16)
    layout.setSpacing(12)

    self.label = QLabel(message)
    self.label.setObjectName("legacyDockerPullProgressMessage")
    self.label.setAccessibleName("Docker pull progress message")
    self.label.setWordWrap(True)
    layout.addWidget(self.label)

    self.output_edit = QTextEdit()
    self.output_edit.setObjectName("legacyDockerPullOutput")
    self.output_edit.setAccessibleName("Docker pull output")
    self.output_edit.setReadOnly(True)
    self.output_edit.setMinimumHeight(190)
    self.output_edit.setLineWrapMode(QTextEdit.WidgetWidth)
    self.output_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    layout.addWidget(self.output_edit)

    self.progress_bar = QProgressBar(self)
    self.progress_bar.setObjectName("legacyDockerPullProgressBar")
    self.progress_bar.setAccessibleName("Docker pull progress")
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setMaximum(100)
    self.progress_bar.setMinimumHeight(24)
    layout.addWidget(self.progress_bar)

    self.setLayout(layout)
    self.apply_stylesheet()
    
    frame = self.frameGeometry()
    frame.moveCenter(screen_geometry(self).center())
    self.move(frame.topLeft())
    return
  
  
  def update_progress(self, output, progress):
    self.output_edit.append(output)
    self.output_edit.verticalScrollBar().setValue(self.output_edit.verticalScrollBar().maximum())
    self.progress_bar.setValue(max(0, min(100, progress)))


  def apply_stylesheet(self):
    self.setStyleSheet(self.sender._current_stylesheet)
    return

  
  def on_docker_pull_finished(self, success):
    if success:
      QMessageBox.information(self, 'Docker Pull', 'Docker image pulled successfully.')      
      self.sender.add_log('Docker image pulled successfully.')
    else:
      QMessageBox.warning(self, 'Docker Pull', 'Failed to pull Docker image.\nCheck if Docker is running.')
    self.accept()  # Close the progress dialog
    return



class _DockerUtilsMixin:
  def __init__(self):
    super().__init__()
    
    self.init_directories()
    
    self.docker_commands = DockerCommandHandler(DOCKER_CONTAINER_NAME)

    self.node_addr = None
    self.node_eth_address = None
    self.container_last_run_status = None
    self.docker_container_name = DOCKER_CONTAINER_NAME
    self.docker_tag = DOCKER_TAG
    self.node_id = self.get_node_id()
    self._dev_mode = False
    
    self.run_with_sudo = False
    
    return
  
  def init_directories(self):
    path = get_user_folder()
    path.mkdir(exist_ok=True)
    self.env_file = path / '.env'
    os.chdir(path)
    self.add_log(f'Working directory: {os.getcwd()}')
    return
  
  
  def post_launch_setup(self):
    self.add_log('Executing post-launch setup...')
    return
  
  def docker_initialize(self):
    self._use_gpus = self.check_nvidia_gpu_available()
    self.__generate_env_file()
    self.__setup_docker_run()
    return
  
  def check_nvidia_gpu_available(self):
    result = False
    try:
      output = check_output_no_window(['nvidia-smi', '-L'], timeout=GPU_CHECK_TIMEOUT_SECONDS)
      result = 'GPU' in output
    except Exception as exc:
      result = False
      output = str(exc)
    output = output.replace('\n', '') 
    self.add_log(f'NVIDIA GPU available: {result} ({output})')
    return result
  
  
  def __setup_docker_run(self):
    self.add_log('Setting up Docker run command...')
    self.docker_image = DOCKER_IMAGE + ":" + self.docker_tag
    
    # Base Docker commands.
    base_clean = ['docker', 'rm', self.docker_container_name]
    base_stop = ['docker', 'stop']
    base_inspect = ['docker', 'inspect', '--format', '{{.State.Running}}', self.docker_container_name]
    
    if self._use_gpus:
      str_gpus = '--gpus=all'
      self.add_log('Using GPU.')
    else:
      str_gpus = ''
      self.add_log('Not using GPU.')
    
    base_run = ['docker', 'run']
    if len(str_gpus) > 0:
      base_run += [str_gpus]
    
    if platform.machine() in ['aarch64', 'arm64']:
        base_run += ['--platform', 'linux/amd64']
    
    base_run += [
        '--rm',
        '--gpus', 'all',
        '-v', f'{DOCKER_VOLUME}:/edge_node/_local_cache',
        '--name', self.docker_container_name, '-d',
    ]
    
    # Add sudo if needed
    if self.run_with_sudo:
      base_clean.insert(0, 'sudo')
      base_stop.insert(0, 'sudo')
      base_inspect.insert(0, 'sudo')
      base_run.insert(0, 'sudo')
    
    self.__CMD_CLEAN = base_clean
    self.__CMD_STOP = base_stop
    self.__CMD_INSPECT = base_inspect
    self.__CMD = base_run
    
    run_cmd = " ".join(self.get_cmd())
    
    self.add_log('Docker run command setup complete:')
    self.add_log(' - Run:     {}'.format(run_cmd))
    self.add_log(' - Clean:   {}'.format(" ".join(self.__CMD_CLEAN)))
    self.add_log(' - Stop:    {}'.format(" ".join(self.__CMD_STOP)))
    self.add_log(' - Inspect: {}'.format(" ".join(self.__CMD_INSPECT)))
    return
  
  
  def get_cmd(self):
    if self._dev_mode:
      result = self.__CMD + ['-p', '80:80', self.docker_image]
    else:
      result = self.__CMD + [self.docker_image]
    return result
  
  def get_clean_cmd(self):
    return self.__CMD_CLEAN
  
  
  def get_stop_command(self):
    return self.__CMD_STOP
  
  
  def get_inspect_command(self):
    return self.__CMD_INSPECT
  
  
  def __maybe_docker_pull(self):
    architecture = platform.machine()
    docker_pull_command = ['docker', 'pull', self.docker_image]
    if architecture == 'aarch64' or architecture == 'arm64':
      docker_pull_command.insert(2, '--platform')
      docker_pull_command.insert(3, 'linux/amd64')

    str_docker_pull_command = ' '.join(docker_pull_command)
    progress_dialog = ProgressBarWindow(f"Pulling Docker Image: '{str_docker_pull_command}'", self._icon, self)
    self.docker_pull_thread = DockerPullThread(docker_pull_command=docker_pull_command)
    self.docker_pull_thread.progress_update.connect(progress_dialog.update_progress)
    self.docker_pull_thread.pull_finished.connect(progress_dialog.on_docker_pull_finished)
    
    self.docker_pull_thread.start()
    
    self.progress_dialog = progress_dialog
    self.progress_dialog.exec_()
    return
  
  
  def get_node_id(self):
    return 'ratio1_' + str(uuid4())[:8]
  

  def __check_env_keys(self):
    # Load the current .env file
    env_vars = OrderedDict()
    try:
      with open(self.env_file, 'r') as file:
        for line in file:
          if line.strip() and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            env_vars[key] = value
    except FileNotFoundError:
      QMessageBox.warning(self, 'Error', '.env file not found.')
      return False
    return True
    
    
  def __generate_env_file(self):
    self.add_log(f'Checking {self.env_file} file...')
    if os.path.exists(self.env_file):
      pass
    else:
      str_env = ENV_TEMPLATE.format(
        self.node_id, 
      )
      with open(self.env_file, 'w') as f:
        f.write(str_env)    
    return

  def check_docker(self):
    """Check if Docker is installed and running.
    
    Returns:
        tuple: (is_installed, is_running, error_message)
            - is_installed: bool indicating if Docker is installed
            - is_running: bool indicating if Docker daemon is running
            - error_message: str with error details if any, None otherwise
    """
    self.add_log('Checking Docker status...')
    try:
        # First check if Docker is installed
        try:
            output = check_output_no_window(['docker', '--version'], timeout=DOCKER_CHECK_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return False, False, f"Docker version check timed out after {DOCKER_CHECK_TIMEOUT_SECONDS} seconds"
        except subprocess.CalledProcessError as exc:
            return False, False, f"Docker version check failed: {exc.output or exc}"
        self.add_log("Docker version: " + output.strip())
        
        # Then check if Docker daemon is running
        try:
            check_output_no_window(['docker', 'info'], timeout=DOCKER_CHECK_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return True, False, f"Docker daemon check timed out after {DOCKER_CHECK_TIMEOUT_SECONDS} seconds"
        except subprocess.CalledProcessError:
            return True, False, "Docker daemon is not running"
        
        self.add_log("Docker daemon is running")
        return True, True, None
    except FileNotFoundError:
        return False, False, "Docker is not installed"


  def is_container_running(self):
    try:
      inspect_cmd = self.get_inspect_command()
      status = check_output_no_window(inspect_cmd, timeout=DOCKER_CHECK_TIMEOUT_SECONDS)

      status = status.strip()
      container_running = status.split()[-1] == 'true'
      if container_running != self.container_last_run_status:
        self.add_log('Edge Node container status changed: {} -> {} (status: {})'.format(
          self.container_last_run_status, container_running, status
        ))
        self.container_last_run_status = container_running
        if container_running:
          self.post_launch_setup()
      return container_running
    except subprocess.TimeoutExpired:
      self.add_log(f'Container status check timed out after {DOCKER_CHECK_TIMEOUT_SECONDS} seconds', debug=True, color="red")
      return False
    except:
      return False


  def launch_container(self):
    print('launch_container')
    is_installed, is_running, error_message = self.check_docker()
    if not (is_installed and is_running):
      if error_message:
        self.add_log(f'Docker is not ready: {error_message}')
      QMessageBox.warning(self, 'Docker Status', error_message or 'Docker is not ready.')
      return

    is_env_ok = self.__check_env_keys()
    if not is_env_ok:
        self.add_log('Environment is not ok. Could not start the container.')
        return

    self.add_log('Updating image...')
    self.__maybe_docker_pull()
    # first try to clean the container
    self.add_log("Attempting to clean up the container...")
    clean_cmd = self.get_clean_cmd()
    try:
      output = check_output_no_window(clean_cmd, timeout=DOCKER_CLEANUP_TIMEOUT_SECONDS)
      self.add_log('Container cleanup status: {}'.format(output))
    except subprocess.TimeoutExpired:
      self.add_log(
        f'Edge Node container cleanup timed out after {DOCKER_CLEANUP_TIMEOUT_SECONDS} seconds'
      )
    except subprocess.CalledProcessError as e:
      error_code = e.returncode
      error_output = e.output
      self.add_log('Edge Node container cleanup failed with code={}: {}'.format(error_code, error_output))
    except Exception as e:
      self.add_log('Edge Node container cleanup failed with unknown error: {}'.format(e))
    
    try:
      self.add_log('Starting Edge Node container...')
      run_cmd = self.get_cmd()
      output = check_output_no_window(run_cmd, timeout=DOCKER_LAUNCH_TIMEOUT_SECONDS)
      self.add_log('Container start status: {}'.format(output))
      QMessageBox.information(self, 'Container Launch', 'Container launched successfully.')
      self.add_log('Edge Node container launched successfully.')
      self.post_launch_setup()
      # endif container running
    except subprocess.TimeoutExpired:
      QMessageBox.warning(self, 'Container Launch', 'Failed to launch container')
      self.add_log(
        f'Edge Node container start timed out after {DOCKER_LAUNCH_TIMEOUT_SECONDS} seconds'
      )
    except subprocess.CalledProcessError as e:
      error_code = e.returncode
      error_output = e.output
      QMessageBox.warning(self, 'Container Launch', 'Failed to launch container')
      self.add_log('Edge Node container start failed with error code={}: {}'.format(error_code, error_output))
    except Exception as e:
      QMessageBox.warning(self, 'Container Launch', 'Failed to launch container')
      self.add_log('Edge Node container start failed with unknown error: {}'.format(e))
    return


  def stop_container(self, container_name=None):
    try:
      name_to_stop = container_name or self.docker_container_name
      self.add_log(f'Stopping Edge Node container {name_to_stop}...')
      stop_cmd = self.get_stop_command() + [name_to_stop]  # Append container name to stop command
      
      check_output_no_window(stop_cmd, timeout=DOCKER_STOP_TIMEOUT_SECONDS)
      sleep(2)
      QMessageBox.information(self, 'Container Stop', 'Container stopped successfully.')      
      self.add_log('Edge Node container stopped successfully.')
      try:
        self.add_log('Cleaning Edge Node container...')
        clean_cmd = self.get_clean_cmd()
        if container_name:
          # Replace the default container name with the provided one
          clean_cmd = clean_cmd[:-1] + [name_to_stop]
        check_output_no_window(clean_cmd, timeout=DOCKER_CLEANUP_TIMEOUT_SECONDS)
        self.add_log('Edge Node container removed.')
      except subprocess.TimeoutExpired:
        self.add_log(
          f'Edge Node container removal timed out after {DOCKER_CLEANUP_TIMEOUT_SECONDS} seconds'
        )
      except subprocess.CalledProcessError:
        self.add_log('Edge Node container removal failed probably due to already being removed.')
    except subprocess.TimeoutExpired:
      QMessageBox.warning(self, 'Container Stop', 'Failed to stop container.')
      self.add_log(f'Edge Node container stop timed out after {DOCKER_STOP_TIMEOUT_SECONDS} seconds.')
    except subprocess.CalledProcessError:
      QMessageBox.warning(self, 'Container Stop', 'Failed to stop container.')
      self.add_log('Edge Node container stop failed.')
    return
