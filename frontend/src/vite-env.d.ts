/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string;
  readonly VITE_DEV_PROXY_TARGET?: string;
  readonly VITE_BUILD_SOURCEMAP?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
