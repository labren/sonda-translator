# sonda-translator
Novo Sonda Translator

# Instalar sshfs
```bash
sudo apt-get install sshfs
```

# Montar o diretório remoto do servidor ftp
```bash
mkdir ftp
sshfs -p 22 labren@150.163.105.82:/mnt/ftp/ ftp/
```