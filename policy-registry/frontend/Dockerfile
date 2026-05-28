FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.d/40-build-info.sh /docker-entrypoint.d/40-build-info.sh
RUN chmod +x /docker-entrypoint.d/40-build-info.sh
# ECharts must exist in static/ (run: just frontend-echarts) so charts work without CDN
COPY static/echarts.min.js /usr/share/nginx/html/echarts.min.js
COPY static /usr/share/nginx/html
