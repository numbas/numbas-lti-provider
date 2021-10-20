update_locales:
	python manage.py makemessages -v0 --locale en
	python manage.py makemessages --locale en -v0 -d djangojs -i "doc/*" -i "media/*" -i bootstrap -i vue.js -i "numbas_lti/static/jsi18n/*" -i "static/*"
	python manage.py compilemessages -v0
	python manage.py compilejsi18n -p numbas_lti -o numbas_lti/static/jsi18n -v0
