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

        pythonPath = "${python}/${python.sitePackages}:$PWD/server:$PWD/insides:$PWD/parser:$PWD/preprocessing:$PWD/ranking_module/src";

        python = pythonPkg.withPackages (
          ps: with ps; [
            # Backend
            fastapi
            pydantic
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
            pymupdf
            trafilatura
            feedparser
            httpx
            pydantic-settings
          ]
        );

        backend = pkgs.writeShellApplication {
          name = "alfa-hack-backend";

          runtimeInputs = [
            pkgs.git
            python
          ];

          text = ''
            set -e

            cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

            export PYTHONPATH="${pythonPath}"

            export HF_HOME="''${HF_HOME:-$PWD/.cache/huggingface}"
            export HF_HUB_CACHE="''${HF_HUB_CACHE:-$HF_HOME/hub}"
            export TRANSFORMERS_CACHE="''${TRANSFORMERS_CACHE:-$HF_HOME/transformers}"

            mkdir -p "$HF_HOME"

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
