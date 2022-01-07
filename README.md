# freepbx_speechanalytics_api
API for SpeechAnalytics integration with FreePBX/Asterisk

1. Скопировать файл settings.py.sample в settings.py и отредактировать параметры
2. Запустить install.sh чтобы установить окружение python с нужными библиотеками
3. Скопировать файл SyetemD юнита из cotrib/systemd в /etc/systemd/system 
4. Запустить сервис 'systemctl start saapi'

Для включения записи в стерео формате скопируйте контект sub-record-check в файл extensions_override_freepbx.conf и вместо строки с вызовом MixMonitor добавьте следующие строки:
```
exten => recordcheck,n,Set(MONFILE=${MIXMON_DIR}${YEAR}/${MONTH}/${DAY}/${CALLFILENAME})
exten => recordcheck,n,MixMonitor(${MONFILE}.${MON_FMT},Sr(${MONFILE}-in.${MON_FMT})t(${MONFILE}-out.${MON_FMT})a${EVAL({MONITOR_REC_OPTION})}i(LOCAL_MIXMON_ID)${MIXMON_BEEP},${EVAL({MIXMON_POST})})
```

В конфигурацию web-сервера /etc/httpd/httpd.conf добавьте проксирование запросов в API (можно также использовать выделенный VirtualHost или nginx на отдельном порту для проксирования):
```
ProxyPreserveHost On
ProxyPass /speechanalytics/api http://127.0.0.1:5005 connectiontimeout=5 timeout=30
ProxyPassReverse /speechanalytics/api http://127.0.0.1:5005
```

Поддержка в чате: https://t.me/iqtek_qa
