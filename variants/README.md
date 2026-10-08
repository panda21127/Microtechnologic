# Вариант 5. Сервис отправлений

Реализуйте создание и отправку. Один заказ создает не более одного отправления;
отправить можно только объект в `created`. Тесты: создание, короткий адрес (422),
дубликат заказа (409), отправка, неизвестное отправление (404).



##
# You should look at the following URL's in order to grasp a solid understanding
# of Nginx configuration files in order to fully unleash the power of Nginx.
# https://www.nginx.com/resources/wiki/start/
# https://www.nginx.com/resources/wiki/start/topics/tutorials/config_pitfalls/

upstream backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
}

server {
    listen 127.0.0.1:8080;
    server_name localhost 127.0.0.1;
    return 308 https://$host:8443$request_uri;
}

server {
    listen 127.0.0.1:8443 ssl;
    server_name localhost 127.0.0.1;
    ssl_certificate     /workspaces/Microtechnologic/certs/dev-cert.pem;
    ssl_certificate_key /workspaces/Microtechnologic/certs/dev-key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 1m;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-ID $request_id;
        proxy_connect_timeout 2s;
        proxy_read_timeout 5s;
    }
}