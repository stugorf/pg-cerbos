FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
# ECharts must exist in static/ (run: just frontend-echarts) so charts work without CDN
COPY static/echarts.min.js /usr/share/nginx/html/echarts.min.js
COPY static /usr/share/nginx/html