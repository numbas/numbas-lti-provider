update_locales:
	python manage.py makemessages -v0
	python manage.py makemessages -d djangojs -i "doc/*" -i "media/*" -i bootstrap -i vue.js -i "numbas_lti/static/jsi18n/*" -i "static/*"
	python manage.py compilemessages -v0
	python manage.py compilejsi18n -p numbas_lti -o numbas_lti/static/jsi18n -v0
