import os

import uvicorn


def main():
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        reload=bool(os.environ.get("RELOAD", "")),
    )


if __name__ == "__main__":
    main()