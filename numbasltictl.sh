#!/bin/bash

# +----------------------------------------------------------------+
# | Program to control the numbas lti docker installation          |
# | Richard Marshall                                               |
# | Nov 2024                                                       |
# +----------------------------------------------------------------+

# https://docs.numbas.org.uk/lti/en/latest/installation/docker.html



PROGNAME="$(basename "$0")"
CURRENT_TIME="$(date +"%F-%T")"
NUMBASLTI_INSTALL_DIRECTORY="/opt/numbas-lti-provider-docker"


usage () {
cat <<EOF

$PROGNAME: usage: $PROGNAME [-h|--help] [<command>]
 
Control the numbas lti docker installation.

COMMAND:
install     Run installation script to setup DB & superuser acc.
upgrade     Upgrade numbas-lti.  Takes circa 10 minutes.
start       Docker compose up commands.
stop        Docker compose down commands.
restart     Calls stop command, followed by start command.
status      Docker status commands.

EOF
return
}



install () {

  # 1. Run installation script, to setup DB & superuser acc.
  cd $NUMBASLTI_INSTALL_DIRECTORY
  docker compose run --rm numbas-setup python ./install

}


upgrade () {

  # 1. Navigate to docker compose directory.
  cd $NUMBASLTI_INSTALL_DIRECTORY

  # 2.Download new software files.
  git pull

  # 3. Remake the container image.
  docker build . --no-cache -t numbas/numbas-lti-provider

  # 4. Run installation script again
  docker compose run –rm numbas-setup python ./install

  # 5. Restart the containers
  docker compose stop
  docker compose start

}

start () {

  cd $NUMBASLTI_INSTALL_DIRECTORY
  docker compose up -d --scale daphne=4 --scale huey=2

}


stop () {

  cd $NUMBASLTI_INSTALL_DIRECTORY
  docker compose down

}


restart () {

  stop
  start

}


status () {

  cd $NUMBASLTI_INSTALL_DIRECTORY
  docker container ls

}





#
# 1. READ PARAMETERS
# ------------------
#


case "$1" in
  -h | --help)  usage
                exit
                ;;
  install)      install
                shift
                ;;
  upgrade)      upgrade
                shift
                ;;
  start)        start
                shift
                ;;
  stop)         stop
                shift
                ;;
  restart)      restart
                shift
                ;;
  status)       status
                shift
                ;;
  *)            usage
                exit
esac

if [[ -n "$1" ]]; then
  echo -e "\nError: Extra parameter ignored: $1.\n"
  sleep 2
  usage
fi
