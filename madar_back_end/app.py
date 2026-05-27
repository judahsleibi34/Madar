from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.auth_routes import router as auth_router
from routes.user_routes import router as user_router
from routes.website_routes import router as website_router
from routes.password_routes import router as password_router
from routes.server_status_routes import router as server_status_router
from routes.contact_routes import router as contact_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def madar_status():
    return {"message": "All working"}


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(website_router)
app.include_router(password_router)
app.include_router(server_status_router)
app.include_router(contact_router)