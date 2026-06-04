@echo off
hostname
ipconfig /all
route print
arp -a
ping 127.0.0.1
pause
