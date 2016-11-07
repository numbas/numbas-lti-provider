### With nginx instead of Apache

In `/etc/nginx/nginx.conf`, add before the end of the `http` block:

```
        # connection upgrade
        map $http_upgrade $connection_upgrade {
                default upgrade;
                '' close;
        }
```

Edit `/etc/nginx/sites-available/default`

(change the `ssl_certificate` paths if you didn't make a self-signed certificate)

```
server {
    listen 443 ssl;
    listen [::]:443 ssl default_server;
    client_max_body_size 20M;

    ssl_certificate /etc/ssl/certs/server.crt;
    ssl_certificate_key /etc/ssl/private/server.key;

    root /srv/numbas-lti-static;

    # Add index.php to the list if you are using PHP
    index index.html index.htm index.nginx-debian.html;

    server_name _;

    location /static/ {
        alias /srv/numbas-lti-static/;
    }
    
    location /websocket/ {
        proxy_pass http://0.0.0.0:8707;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }

    location / {
        proxy_pass http://0.0.0.0:8707;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 1;
        proxy_send_timeout 30;
        proxy_read_timeout 30;
        proxy_redirect http:// $scheme://;
    }
}
```

Reload `nginx`:

```
sudo service nginx restart
```


