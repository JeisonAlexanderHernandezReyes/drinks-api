import pytest
from fastapi.testclient import TestClient
import os
import json
import sys

# Add the app directory to path so we can import main
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.main import app, DrinkStorage

# Create a test client
client = TestClient(app)

# Test data fixture
@pytest.fixture
def test_drink_storage():
    # Create a temporary file for testing
    test_file = "test_drinks.json"
    
    # Create a test storage with known data
    storage = DrinkStorage(test_file)
    storage.drinks = [
        {"id": 1, "name": "Test Espresso", "size": "S", "price": 2.0},
        {"id": 2, "name": "Test Latte", "size": "M", "price": 3.0}
    ]
    storage.next_id = 3
    storage.save_data()
    
    yield storage
    
    # Cleanup after tests
    if os.path.exists(test_file):
        os.remove(test_file)

# Override dependency in tests
@pytest.fixture
def override_get_drink_storage(test_drink_storage):
    app.dependency_overrides = {}
    
    def get_test_storage():
        return test_drink_storage
    
    # Cambio clave: sobrescribir get_drink_storage, no DrinkStorage
    from app.main import get_drink_storage
    app.dependency_overrides[get_drink_storage] = get_test_storage
    
    yield
    app.dependency_overrides = {}

# Tests
def test_read_root():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to VirtualCoffee Drinks API"}

def test_get_menu(override_get_drink_storage):
    """Test getting the full menu."""
    response = client.get("/menu")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Test Espresso"
    assert data[1]["name"] == "Test Latte"

def test_get_drink_by_name_found(override_get_drink_storage):
    """Test searching for a drink by name that exists."""
    response = client.get("/menu/Test Latte")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Latte"
    assert data[0]["size"] == "M"
    assert data[0]["price"] == 3.0

def test_get_drink_by_name_not_found(override_get_drink_storage):
    """Test searching for a drink by name that doesn't exist."""
    response = client.get("/menu/NonExistentDrink")
    assert response.status_code == 404
    assert response.json() == {"detail": "Drink not found"}

def test_add_valid_drink(override_get_drink_storage):
    """Test adding a valid drink."""
    new_drink = {
        "name": "Mocha",
        "size": "L",
        "price": 4.0
    }
    response = client.post("/menu", json=new_drink)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 3
    assert data["name"] == "Mocha"
    assert data["size"] == "L"
    assert data["price"] == 4.0
    
    # Verify it was added to the menu
    menu_response = client.get("/menu")
    menu = menu_response.json()
    assert len(menu) == 3
    assert any(drink["name"] == "Mocha" for drink in menu)

def test_add_invalid_drink_empty_name():
    """Test adding a drink with an empty name."""
    invalid_drink = {
        "name": "",
        "size": "M",
        "price": 3.0
    }
    response = client.post("/menu", json=invalid_drink)
    assert response.status_code == 422
    detail = response.json()["detail"]
    
    # En lugar de buscar un mensaje específico, solo verificamos que hay un error
    # relacionado con el campo 'name'
    assert any(error["loc"][1] == "name" for error in detail)

def test_add_invalid_drink_negative_price():
    """Test adding a drink with a negative price."""
    invalid_drink = {
        "name": "Negative Coffee",
        "size": "M",
        "price": -1.0
    }
    response = client.post("/menu", json=invalid_drink)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("greater than 0" in error["msg"] for error in detail)

def test_add_invalid_drink_invalid_size():
    """Test adding a drink with an invalid size."""
    invalid_drink = {
        "name": "Invalid Size Coffee",
        "size": "XL",  # Not a valid size
        "price": 5.0
    }
    response = client.post("/menu", json=invalid_drink)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("Size must be S, M, or L" in error["msg"] for error in detail)

# Test DrinkStorage class directly
def test_drink_storage_initialization():
    """Test that DrinkStorage initializes correctly."""
    test_file = "test_storage_init.json"
    
    # Ensure the file doesn't exist
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # Create a new storage
    storage = DrinkStorage(test_file)
    
    # Verify default data was created
    assert len(storage.drinks) > 0
    assert storage.next_id > 1
    
    # Clean up
    os.remove(test_file)

def test_drink_storage_load_save_data():
    """Test saving and loading data."""
    test_file = "test_storage_load_save.json"
    
    # Create initial storage
    storage1 = DrinkStorage(test_file)
    storage1.drinks = [{"id": 10, "name": "TestDrink", "size": "S", "price": 1.0}]
    storage1.next_id = 11
    storage1.save_data()
    
    # Create new storage instance that should load the saved data
    storage2 = DrinkStorage(test_file)
    
    # Verify data was loaded correctly
    assert len(storage2.drinks) == 1
    assert storage2.drinks[0]["name"] == "TestDrink"
    assert storage2.next_id == 11
    
    # Clean up
    os.remove(test_file)

def test_drink_storage_add_drink():
    """Test adding a drink to storage."""
    test_file = "test_storage_add.json"
    storage = DrinkStorage(test_file)
    
    # Save initial state
    initial_count = len(storage.drinks)
    initial_next_id = storage.next_id
    
    # Add a drink
    from app.main import DrinkCreate
    new_drink = DrinkCreate(name="New Test Drink", size="L", price=4.5)
    added_drink = storage.add_drink(new_drink)
    
    # Verify drink was added
    assert len(storage.drinks) == initial_count + 1
    assert storage.next_id == initial_next_id + 1
    assert added_drink["name"] == "New Test Drink"
    assert added_drink["id"] == initial_next_id
    
    # Clean up
    os.remove(test_file)

# Integration tests that simulate the full flow
def test_integration_add_and_retrieve():
    """
    Integration test: Add a drink and then retrieve it by name.
    """
    # Crear un nombre aún más único usando timestamp
    import time
    unique_name = f"SuperUniqueTestDrink_{int(time.time())}"
    
    new_drink = {
        "name": unique_name,
        "size": "M",
        "price": 5.0
    }
    add_response = client.post("/menu", json=new_drink)
    assert add_response.status_code == 201
    
    # Obtener el ID del nuevo elemento
    created_id = add_response.json()["id"]
    
    # Retrieve the drink by name
    get_response = client.get(f"/menu/{unique_name}")
    assert get_response.status_code == 200
    
    # Verificar que la bebida creada está en los resultados
    drinks = get_response.json()
    found = False
    for drink in drinks:
        if drink["id"] == created_id:
            found = True
            assert drink["name"] == unique_name
            assert drink["size"] == "M"
            assert drink["price"] == 5.0
    
    assert found, f"La bebida con ID {created_id} no se encontró en los resultados"