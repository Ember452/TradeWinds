import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 本地开发代理:/api 直连本机 FastAPI,前端无需处理跨域
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
