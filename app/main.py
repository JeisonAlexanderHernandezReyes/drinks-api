# app/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator 
import uvicorn
from datetime import datetime
import json
import os

# Models
class DrinkBase(BaseModel):
    name: str = Field(..., min_length=1, description="Name of the drink")
    size: str = Field(..., description="Size of the drink (S, M, L)")
    price: float = Field(..., gt=0, description="Price of the drink")
    
    field_validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    @field_validator('size')
    def size_must_be_valid(cls, v):
        if v not in ['S', 'M', 'L']:
            raise ValueError('Size must be S, M, or L')
        return v
    
    @field_validator('price')
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        return v

class DrinkCreate(DrinkBase):
    pass

class Drink(DrinkBase):
    id: int
    
    class ConfigDict:
        from_attributes = True

# In-memory storage
class DrinkStorage:
    def __init__(self, data_file="drinks.json"):
        self.data_file = data_file
        self.drinks = []
        self.next_id = 1
        self.load_data()
    
    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.drinks = data.get('drinks', [])
                    self.next_id = data.get('next_id', 1)
            except Exception as e:
                print(f"Error loading data: {e}")
                # Initialize with default data if loading fails
                self._init_default_data()
        else:
            # Initialize with default data if file doesn't exist
            self._init_default_data()
    
    def _init_default_data(self):
    # Comprueba si este es un entorno de prueba (basado en el nombre del archivo)
        if self.data_file.startswith("test_"):
            # En pruebas, inicializar con menos datos
            self.drinks = [
                {"id": 1, "name": "Test Espresso", "size": "S", "price": 2.0},
                {"id": 2, "name": "Test Latte", "size": "M", "price": 3.0}
            ]
            self.next_id = 3
        else:
            # Datos normales para la aplicación
            self.drinks = [
                {"id": 1, "name": "Espresso", "size": "S", "price": 2.5},
                {"id": 2, "name": "Latte", "size": "M", "price": 3.5},
                {"id": 3, "name": "Cappuccino", "size": "M", "price": 3.0},
                {"id": 4, "name": "Americano", "size": "L", "price": 2.8}
            ]
            self.next_id = 5
        self.save_data()
        
    def save_data(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump({
                    'drinks': self.drinks,
                    'next_id': self.next_id
                }, f)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def get_all_drinks(self):
        return self.drinks
    
    def get_drink_by_name(self, name: str):
        return [drink for drink in self.drinks if drink["name"].lower() == name.lower()]
    
    def add_drink(self, drink: DrinkCreate):
        new_drink = {
            "id": self.next_id,
            "name": drink.name,
            "size": drink.size,
            "price": drink.price
        }
        self.drinks.append(new_drink)
        self.next_id += 1
        self.save_data()
        return new_drink

# Application
app = FastAPI(title="VirtualCoffee Drinks API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_drink_storage():
    return DrinkStorage()

# Routes
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to VirtualCoffee Drinks API"}

@app.get("/menu", response_model=List[Drink], tags=["Menu"])
def get_menu(storage: DrinkStorage = Depends(get_drink_storage)):
    """
    Get the full menu of available drinks.
    """
    return storage.get_all_drinks()

@app.get("/menu/{name}", response_model=List[Drink], tags=["Menu"])
def get_drink(name: str, storage: DrinkStorage = Depends(get_drink_storage)):
    """
    Search for drinks by name.
    """
    drinks = storage.get_drink_by_name(name)
    if not drinks:
        raise HTTPException(status_code=404, detail="Drink not found")
    return drinks

@app.post("/menu", response_model=Drink, status_code=201, tags=["Menu"])
def add_drink(drink: DrinkCreate, storage: DrinkStorage = Depends(get_drink_storage)):
    """
    Add a new drink to the menu.
    """
    return storage.add_drink(drink)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)