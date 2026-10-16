# 画面(React)の開発用イメージ。ビルドコンテキストは app/
# 評価環境用の本番ビルドの段は段階6で追加する
FROM node:20

ENV TZ=Asia/Tokyo
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
