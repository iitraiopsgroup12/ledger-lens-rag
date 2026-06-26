import os

import uvicorn


def main():
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        reload=bool(os.environ.get("RELOAD", "")),
        # Chat requests can take a while to process; keep connections alive
        # long enough (30 min default) so slow responses aren't dropped.
        timeout_keep_alive=int(os.environ.get("TIMEOUT_KEEP_ALIVE", "1800")),
    )


if __name__ == "__main__":
    main()