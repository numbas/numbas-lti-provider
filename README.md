# Numbas LTI provider

An LTI tool provider to run Numbas exams. Runs as a [Django Channels](https://github.com/andrewgodwin/channels) app.

**This tool is still in development, and has not been tested with real students. Do not use it for important assessments.**

## Installation instructions

These instructions will create a virtual machine in [Vagrant](https://www.vagrantup.com/), which runs the Numbas LTI provider proxied through nginx.
If you want to run on a real machine, skip the first couple of steps to do with Vagrant.
I used Ubuntu 16.04 - the process of installing packages will be different on different versions or different distributions.

I set up Vagrant to forward port 443 on the host machine to port 443 on the VM. I think this might only work on Windows. I'm not sure how to get it running on a different port - I had problems with the nginx proxy.

Create a directory for the vagrant VM:

```
mkdir numbas_lti
cd numbas_lti
```

Edit `Vagrantfile`:

```
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ubuntu/xenial64"

  config.vm.network :forwarded_port, host: 443, guest: 443
end
```

Start vagrant and ssh into it:

```
vagrant up
vagrant ssh
```

Install packages and set up users:

```
sudo addgroup numbas_lti
sudo adduser ubuntu numbas_lti
sudo adduser ubuntu www-data
sudo apt-get install nginx redis-server postgresql postgresql-server-dev-9.5 libxml2-dev libxslt1-dev python-dev lib32z1-dev python3-pip supervisor git
sudo pip3 install virtualenv

sudo git clone https://github.com/numbas/numbas-lti-provider.git /srv/numbas-lti-provider
sudo chown -R root:numbas_lti /srv/numbas-lti-provider

sudo mkdir /srv/numbas-lti-media
sudo mkdir /srv/numbas-lti-static
sudo chown -R root:numbas_lti /srv/numbas-lti-media
sudo chown -R www-data:www-data /srv/numbas-lti-static
sudo chmod -R 770 /srv/numbas-lti-*

sudo virtualenv /opt/numbas_lti_python
sudo chown -R root:numbas_lti /opt/numbas_lti_python
sudo chmod -R 770 /opt/numbas_lti_python
source /opt/numbas_lti_python/bin/activate
cd /srv/numbas-lti-provider
pip install -r requirements.txt
pip install asgi_redis psycopg2
```

(create postgres database `numbas_lti` and user `numbas_lti`)

```
sudo -i -u postgres
createuser numbas_lti -W
createdb numbas_lti
exit
```

Install [letsencrypt](https://letsencrypt.org/) to obtain an SSL certificate, or [create a self-signed certificate](https://help.ubuntu.com/12.04/serverguide/certificates-and-security.html).

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

Write `/srv/numbas-lti-provider/pretendlti/settings.py`:

(edit the database settings as appropriate)

```
import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'qox=@g2o^ajt)uki^s84c0kk_ljnqcsx6km44209oae)lfhgn+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'numbas_lti',
    'bootstrapform',
]

MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_auth_lti.middleware_patched.MultiLTILaunchAuthMiddleware',
    'numbas_lti.middleware.NumbasLTIResourceMiddleware',
]
AUTHENTICATION_BACKENDS = ['numbas_lti.backends.LTIAuthBackend']

ROOT_URLCONF = 'pretendlti.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'pretendlti.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'numbas_lti',
        'USER': 'numbas_lti',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '',
    }
}


# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-us'
LOCALE_PATHS = (os.path.join(BASE_DIR,'locale'),)

TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

MEDIA_ROOT = '/srv/numbas-lti-media'
MEDIA_URL = '/media/'

STATIC_ROOT = '/srv/numbas-lti-static'
STATIC_URL = 'https://localhost/static/'

# Channels

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "asgi_redis.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get('REDIS_URL','redis://localhost:6379')],
        },
        "ROUTING": "pretendlti.routing.channel_routing",
    },
}

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
```

Write `/srv/numbas-lti-provider/pretendlti/asgi.py`:

```
import os
import channels.asgi

os.environ.setdefault('DJANGO_SETTINGS_MODLE','pretendlti.settings')
channel_layer = channels.asgi.get_channel_layer()
```

Set up database:

```
python manage.py migrate
python manage.py collectstatic --noinput
sudo chown -R www-data:www-data /srv/numbas-lti-static/
```

Set up an LTI consumer key

```
> python manage.py shell
from numbas_lti.models import LTIConsumer
LTIConsumer.objects.create(key='cp',secret='cp')
```

Edit `/srv/numbas-lti-provider/start_daphne.sh`

```
#!/bin/bash
echo "STARTING"
source /opt/numbas_lti_python/bin/activate
cd /srv/numbas-lti-provider
export DJANGO_SETTINGS_MODULE='pretendlti.settings'
daphne pretendlti.asgi:channel_layer --port 8707 --bind 0.0.0.0 -v 2
```

Edit `/srv/numbas-lti-provider/start_worker.sh`

```
#!/bin/bash
source /opt/numbas_lti_python/bin/activate
cd /srv/numbas-lti-provider
export DJANGO_SETTINGS_MODULE='pretendlti.settings'
python manage.py runworker
```

Make `start_` files executable:

```
chmod +x /srv/numbas-lti-provider/start_*.sh
```

Edit `/etc/supervisor/conf.d/numbas_lti.conf`:

```
[program:numbas_lti_daphne]
command=/srv/numbas-lti-provider/start_daphne.sh
autostart=true
autorestart=true

[program:numbas_lti_worker_a]
command=/srv/numbas-lti-provider/start_worker.sh
autostart=true
autorestart=true

[program:numbas_lti_worker_b]
command=/srv/numbas-lti-provider/start_worker.sh
autostart=true
autorestart=true

[program:numbas_lti_worker_c]
command=/srv/numbas-lti-provider/start_worker.sh
autostart=true
autorestart=true

[group:numbas_lti]
programs=numbas_lti_daphne,numbas_lti_worker_a,numbas_lti_worker_b,numbas_lti_worker_c
priority=999
```

Start `supervisor`:

```
sudo service supervisor start
```

The server is now running at `https://localhost`.
