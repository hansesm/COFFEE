# Build the Application

# docker build -t fb_coffee .
# docker build -t ghcr.io/hansesm/fb_coffee:latest -t ghcr.io/hansesm/fb_coffee:v2.5 .
docker buildx build --platform linux/amd64,linux/arm64 --tag ghcr.io/hansesm/fb_coffee:latest --tag ghcr.io/hansesm/fb_coffee:v2.7 --push .


# docker build --no-cache -t fb_coffee .
docker push --all-tags ghcr.io/hansesm/fb_coffee

# docker pull ghcr.io/hansesm/fb_coffee:latest
# Deploy the Application

k delete -f deployment-app.yaml
k create -f deployment-app.yaml

python manage.py makemigrations
python manage.py migrate

python manage.py create_users_and_groups

## Translations ## 
python manage.py makemessages -l de 
python manage.py makemessages -l en
python manage.py compilemessages


# Podman
sudo podman play kube --replace podman-deployment.yaml
sudo podman exec -it feedback-app-pod-feedback-app /bin/bash


# Podman autostart

sudo podman generate systemd --name feedback-app-pod --files

sudo mv pod-feedback-app-pod.service /etc/systemd/system/

sudo systemctl daemon-reload

sudo systemctl enable pod-feedback-app-pod

sudo systemctl start pod-feedback-app-pod

systemctl status pod-feedback-app-pod

# venv
source venv/bin/activate