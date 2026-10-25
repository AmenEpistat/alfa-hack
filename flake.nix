{
  description = "Alfa Hack frontend and FastAPI backend development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs";
    utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      utils,
    }:
    utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        pythonPkg = pkgs.python3;

        tesseract = pkgs.tesseract;

        pythonPath = "${python}/${python.sitePackages}:$PWD/server:$PWD:$PWD/parser/src:$PWD/preprocessing:$PWD/ranking_module/src";

        python = pythonPkg.withPackages (
          ps: with ps; [
            # Backend
            fastapi
            pydantic
            pydantic-settings
            sqlalchemy
            uvicorn

            # ranking_module
            pandas
            numpy
            pyyaml
            jsonschema
            orjson
            scikit-learn
            sentence-transformers
            faiss

            # parser
            pdfplumber
            pypdfium2
            trafilatura
            feedparser
            httpx
          ]
        );

        backend = pkgs.writeShellApplication {
          name = "alfa-hack-backend";

          runtimeInputs = [
            pkgs.git
            python
            tesseract
          ];

          text = ''
            set -e

            cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

            export PYTHONPATH="${pythonPath}"

            export HF_HOME="''${HF_HOME:-$PWD/.cache/huggingface}"
            export HF_HUB_CACHE="''${HF_HUB_CACHE:-$HF_HOME/hub}"
            export TRANSFORMERS_CACHE="''${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"

            export TESSDATA_PREFIX="${tesseract}/share/tessdata"
            export ALPHA_TESSDATA="${tesseract}/share/tessdata"
            export ALPHA_OCR_ENABLED="''${ALPHA_OCR_ENABLED:-true}"
            export ALPHA_OCR_LANGUAGE="''${ALPHA_OCR_LANGUAGE:-rus+eng}"

            mkdir -p "$HF_HOME"

            # LLM configuration.
            export ALPHA_LLM_BASE_URL="''${ALPHA_LLM_BASE_URL:-https://api.alfahack-gateway26.ru/v1}"
            export ALPHA_LLM_FALLBACK_BASE_URL="''${ALPHA_LLM_FALLBACK_BASE_URL:-}"

            # Вручную, пожалуйста
            export ALPHA_LLM_API_KEY="''${ALPHA_LLM_API_KEY:-}"
            export ALPHA_LLM_MODEL="''${ALPHA_LLM_MODEL:-}"

            export ALPHA_LLM_FAMILY="''${ALPHA_LLM_FAMILY:-GLM-5.3-Flash}"
            export ALPHA_LLM_TIMEOUT="''${ALPHA_LLM_TIMEOUT:-45}"
            export ALPHA_LLM_CONNECT_TIMEOUT="''${ALPHA_LLM_CONNECT_TIMEOUT:-5}"
            export ALPHA_LLM_MAX_OUTPUT_TOKENS="''${ALPHA_LLM_MAX_OUTPUT_TOKENS:-4096}"
            export ALPHA_LLM_REASONING_EFFORT="''${ALPHA_LLM_REASONING_EFFORT:-low}"
            export ALPHA_LLM_THINKING_PROTOCOL="''${ALPHA_LLM_THINKING_PROTOCOL:-legacy}"
            export ALPHA_LLM_THINKING_MODE="''${ALPHA_LLM_THINKING_MODE:-default}"
            export ALPHA_LLM_LENGTH_RETRIES="''${ALPHA_LLM_LENGTH_RETRIES:-1}"

            export ALPHA_ALLOW_UNKNOWN_COST="''${ALPHA_ALLOW_UNKNOWN_COST:-true}"
            export ALPHA_DAILY_BUDGET_RUB="''${ALPHA_DAILY_BUDGET_RUB:-500}"

            exec uvicorn app.main:app \
              --app-dir server \
              --reload \
              --host 0.0.0.0 \
              --port "''${BACKEND_PORT:-8000}"
          '';
        };

        frontend = pkgs.writeShellApplication {
          name = "alfa-hack-frontend";

          runtimeInputs = [
            pkgs.nodejs
            pkgs.git
          ];

          text = ''
            set -e

            cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)/client"

            if [ ! -d node_modules ]; then
              npm ci
            fi

            exec npm run dev \
              -- --host 0.0.0.0 \
              --port "''${FRONTEND_PORT:-5173}"
          '';
        };
      in
      {
        packages = {
          backend = backend;
          frontend = frontend;
          default = backend;
        };

        apps = {
          backend = {
            type = "app";
            program = "${backend}/bin/alfa-hack-backend";
          };

          frontend = {
            type = "app";
            program = "${frontend}/bin/alfa-hack-frontend";
          };

          default = {
            type = "app";
            program = "${backend}/bin/alfa-hack-backend";
          };
        };

        devShells.default = pkgs.mkShell {
          name = "alfa-hack";

          packages = [
            python
            pkgs.nodejs
            pkgs.git
          ];

          shellHook = ''
            export PYTHONPATH="${pythonPath}"

            export HF_HOME="''${HF_HOME:-$PWD/.cache/huggingface}"
            export HF_HUB_CACHE="''${HF_HUB_CACHE:-$HF_HOME/hub}"
            export TRANSFORMERS_CACHE="''${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"

            export VITE_API_URL="''${VITE_API_URL:-http://localhost:8000}"

            mkdir -p "$HF_HOME"

            echo "Alfa Hack development shell"
            echo ""
            echo "Backend:"
            echo "  nix run .#backend"
            echo ""
            echo "Frontend:"
            echo "  nix run .#frontend"
          '';
        };
      }
    );
}
