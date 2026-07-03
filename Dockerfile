# Optional: build a self-contained image (portable to any container host).
# The docker-compose.yml bind-mount path doesn't need this; use it if you'd
# rather ship an image than mount a file.
#
#   docker build -t clock-tuner .
#   docker run -d --name clock-tuner -p 8099:80 clock-tuner
FROM nginx:alpine
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 80
