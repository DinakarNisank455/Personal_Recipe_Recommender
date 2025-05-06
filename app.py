from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify,make_response
import io
import pymysql
from datetime import datetime, timedelta
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from difflib import get_close_matches
import re
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

app = Flask(__name__)

# Secret Key & Session Config
app.secret_key = "secret_key"
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
Session(app)

# API Keys
app_id = "9339488b"  
app_key = "4f804a4822c6c387579112bcda286297"  

YOUTUBE_API_KEY = "AIzaSyB0-_00000000000000000000000000000000"

# Common ingredients and recipe names for spelling correction
COMMON_INGREDIENTS = [
    'chicken', 'beef', 'pork', 'lamb', 'turkey', 'fish', 'salmon', 'tuna', 'shrimp',
    'rice', 'pasta', 'bread', 'potato', 'tomato', 'onion', 'garlic', 'carrot',
    'broccoli', 'spinach', 'lettuce', 'cheese', 'milk', 'butter', 'egg', 'flour',
    'sugar', 'salt', 'pepper', 'oil', 'vinegar', 'honey', 'chocolate', 'vanilla',
    'cinnamon', 'basil', 'oregano', 'thyme', 'rosemary', 'parsley', 'cilantro'
]

COMMON_RECIPE_NAMES = [
    'pasta', 'salad', 'soup', 'stew', 'curry', 'casserole', 'roast', 'grill',
    'bake', 'fry', 'steam', 'boil', 'stir-fry', 'sandwich', 'burger', 'pizza',
    'lasagna', 'risotto', 'quiche', 'omelet', 'pancake', 'waffle', 'muffin',
    'cookie', 'cake', 'pie', 'bread', 'roll', 'bun'
]

def correct_spelling(query, search_type='ingredients'):
    """Correct spelling in search query using fuzzy matching."""
    words = query.lower().split()
    corrected_words = []
    suggestions = []
    
    # Choose the appropriate dictionary based on search type
    dictionary = COMMON_RECIPE_NAMES if search_type == 'name' else COMMON_INGREDIENTS
    
    for word in words:
        # Clean the word of any special characters
        clean_word = re.sub(r'[^a-zA-Z]', '', word)
        if not clean_word:
            continue
            
        # Get close matches
        matches = get_close_matches(clean_word, dictionary, n=1, cutoff=0.8)
        
        if matches and matches[0] != clean_word:
            corrected_words.append(matches[0])
            suggestions.append(f"'{word}' → '{matches[0]}'")
        else:
            corrected_words.append(word)
    
    corrected_query = ' '.join(corrected_words)
    return corrected_query, suggestions

# Database Connection
def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="@Bunny455",
        database="prr",
        autocommit=True
    )


ALLERGENS = {
    'dairy': ['milk', 'cheese', 'yogurt', 'butter', 'cream', 'whey', 'casein'],
    'eggs': ['egg', 'albumin', 'mayonnaise'],
    'fish': ['fish', 'anchovy', 'tuna', 'salmon', 'cod'],
    'shellfish': ['shrimp', 'crab', 'lobster', 'prawn', 'shellfish'],
    'tree_nuts': ['almond', 'walnut', 'pecan', 'cashew', 'pistachio', 'hazelnut'],
    'peanuts': ['peanut', 'arachis'],
    'wheat': ['wheat', 'flour', 'bread', 'pasta', 'couscous', 'semolina'],
    'soy': ['soy', 'soya', 'tofu', 'edamame', 'miso'],
    'sesame': ['sesame', 'tahini']
}

def detect_allergens(ingredients):
    detected_allergens = set()
    ingredients_text = ' '.join(ingredients).lower()
    
    for allergen, keywords in ALLERGENS.items():
        if any(keyword in ingredients_text for keyword in keywords):
            detected_allergens.add(allergen.replace('_', ' ').title())
    
    return list(detected_allergens)

# Unique User ID
def generate_user_id():
    db = get_db_connection()
    with db.cursor() as cursor:
        today = datetime.today().strftime('%Y%m%d')
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_id LIKE %s", (today + "%",))
        count = cursor.fetchone()[0] + 1
    db.close()
    return f"{today}{count:03d}"

# Home
@app.route("/")
def home():
    return render_template("index.html")

# Signup
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("Confirm_password")

        if not all([name, email, password, confirm_password]):
            flash("⚠️ Please fill in all required fields!", "error")
            return redirect(url_for("signup"))

        if confirm_password != password:
            flash("⚠️ Passwords do not match!", "error")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)
        user_id = generate_user_id()

        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("⚠️ User already exists!", "error")
                return redirect(url_for("signup"))

            cursor.execute(
                "INSERT INTO users (user_id, email, password) VALUES (%s, %s, %s)",
                (user_id, email, hashed_password)
            )
        db.close()

        flash("✅ Signup successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

#  Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("⚠️ Please enter both email and password.", "error")
            return redirect(url_for("login"))

        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute("SELECT user_id, password FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        db.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            flash("✅ Login successful!", "success")
            return redirect(url_for("dashboard"))

        flash("⚠️ Invalid credentials.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")

# Forgot Password
@app.route('/forgot_password', methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        new_password = request.form["new_password"]
        hashed_password = generate_password_hash(new_password)

        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))
        db.close()

        flash('✅ Password reset successful. Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

# 🔹 Dashboard
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("⚠️ Please log in to access the dashboard.", "error")
        return redirect(url_for("login"))

    db = get_db_connection()
    with db.cursor() as cursor:
        # Get user information
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (session["user_id"],))
        user = cursor.fetchone()

        # Get saved recipes count
        cursor.execute("SELECT COUNT(*) FROM saved_recipes WHERE user_id = %s", (session["user_id"],))
        saved_recipes_count = cursor.fetchone()[0]

        # Get grocery list count
        cursor.execute("SELECT COUNT(*) FROM grocery_lists WHERE user_id = %s", (session["user_id"],))
        grocery_list_count = cursor.fetchone()[0]

        # Get total calories from saved recipes
        cursor.execute("""
            SELECT COALESCE(SUM(CAST(calories AS DECIMAL)), 0) as total_calories 
            FROM saved_recipes 
            WHERE user_id = %s
        """, (session["user_id"],))
        total_calories = cursor.fetchone()[0]

        # Get recent activity
        cursor.execute("""
            (SELECT 'saved_recipe' as type, recipe_name as description, saved_at as time, '📚' as icon
            FROM saved_recipes 
            WHERE user_id = %s)
            UNION ALL
            (SELECT 'grocery_list' as type, 'Generated grocery list' as description, created_at as time, '🛒' as icon
            FROM grocery_lists 
            WHERE user_id = %s)
            ORDER BY time DESC
            LIMIT 5
        """, (session["user_id"], session["user_id"]))
        recent_activity = cursor.fetchall()

    db.close()

    return render_template("dashboard.html",
                         user=user,
                         saved_recipes_count=saved_recipes_count,
                         grocery_list_count=grocery_list_count,
                         total_calories=total_calories,
                         recent_activity=recent_activity)

#  Recipe Search

@app.route("/recipe_search", methods=['GET'])
def recipe_search():
    return render_template('recipe_search.html')


@app.route("/select_search", methods=["POST"])
def select_search():
    selected_type = request.form.get("search_type")
    if selected_type == "nutrition":
        return redirect(url_for('nutrition_search'))
    elif selected_type == "ingredient":
        return redirect(url_for('ingredient_search'))
    else:
        flash("⚠️ Invalid selection. Please try again.", "error")
        return redirect(url_for('nutrition_search'))

def is_duplicate_recipe(recipe, seen_recipes):
    """
    Check if a recipe is a duplicate by comparing multiple attributes.
    Returns True if it's a duplicate, False otherwise.
    """
    # Create a unique identifier based on multiple attributes
    recipe_signature = {
        'name': recipe.get("label", "Unknown Recipe").lower(),
        'ingredients': sorted([ing.lower() for ing in recipe.get("ingredientLines", [])]),
        'calories': round(float(recipe.get("calories", 0))),
        'protein': round(float(recipe.get("totalNutrients", {}).get("PROCNT", {}).get("quantity", 0) or 0)),
        'fat': round(float(recipe.get("totalNutrients", {}).get("FAT", {}).get("quantity", 0) or 0)),
        'carbs': round(float(recipe.get("totalNutrients", {}).get("CHOCDF", {}).get("quantity", 0) or 0))
    }
    
    # Convert to tuple for hashing
    recipe_key = (
        recipe_signature['name'],
        tuple(recipe_signature['ingredients'][:5]),  # Compare first 5 ingredients
        recipe_signature['calories'],
        recipe_signature['protein'],
        recipe_signature['fat'],
        recipe_signature['carbs']
    )
    
    if recipe_key in seen_recipes:
        return True
    
    seen_recipes.add(recipe_key)
    return False

# Recipe Search by Ingredients
@app.route("/ingredient_search", methods=["GET", "POST"])
def ingredient_search():
    search_performed = False
    spelling_suggestions = []

    if request.method == "POST":
        search_performed = True
        search_type = request.form.get('search_type', 'ingredients')
        search_query = request.form.get('ingredients', '').strip()
        diet_filter = request.form.get('diet_filter', '')
        
        if not search_query:
            flash("⚠️ Please enter a search term!", "error")
            return render_template("ingredient_search.html", recipes=[], search_performed=search_performed)

        # Apply spelling correction
        corrected_query, spelling_suggestions = correct_spelling(search_query, search_type)
        
        if spelling_suggestions:
            flash(f"💡 Spelling suggestions: {', '.join(spelling_suggestions)}", "info")
            search_query = corrected_query

        try:
            # Common recipe categories and ingredients for suggestions
            common_categories = {
                'meat': ['chicken', 'beef', 'pork', 'lamb', 'turkey'],
                'vegetables': ['carrots', 'potatoes', 'tomatoes', 'onions', 'broccoli'],
                'grains': ['rice', 'pasta', 'bread', 'quinoa', 'couscous'],
                'cuisines': ['italian', 'chinese', 'indian', 'mexican', 'thai'],
                'dishes': ['soup', 'salad', 'curry', 'stew', 'casserole']
            }

            # Clean and format the search query
            if search_type == 'name':
                # For recipe names, try to extract main ingredients or categories
                query_parts = search_query.lower().split()
                main_ingredient = next((word for word in query_parts if word in [item for sublist in common_categories.values() for item in sublist]), None)
                
                if main_ingredient:
                    # If we found a main ingredient, use it to generate suggestions
                    suggestions = []
                    for category, items in common_categories.items():
                        if main_ingredient in items:
                            suggestions.extend([f"{main_ingredient} {dish}" for dish in common_categories['dishes']])
                            break
                else:
                    # If no main ingredient found, suggest based on common categories
                    suggestions = [f"{ingredient} {dish}" for ingredient in common_categories['meat'] for dish in common_categories['dishes']]
                
                api_url = f"https://api.edamam.com/api/recipes/v2?q={search_query}&app_id={app_id}&app_key={app_key}&type=public"
            else:
                # For ingredients search, clean and format ingredients
                ingredients = [ingredient.strip().lower() for ingredient in search_query.split(",")]
                ingredients_query = ",".join(ingredients)
                
                # Generate suggestions based on ingredient categories
                suggestions = []
                for ingredient in ingredients:
                    for category, items in common_categories.items():
                        if ingredient in items:
                            suggestions.extend([f"{ingredient}, {other}" for other in items if other != ingredient])
                
                api_url = f"https://api.edamam.com/api/recipes/v2?app_id={app_id}&app_key={app_key}&type=public&ingr={ingredients_query}"
            
            # Add diet filter if specified
            if diet_filter:
                api_url += f"&diet={diet_filter}"
            
            print(f"API URL: {api_url}")
            
            response = requests.get(api_url)
            print(f"Response Status: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            print(f"Response Data: {data.keys() if data else 'No data'}")

            if not data or "hits" not in data or not data["hits"]:
                if search_type == 'name':
                    flash(f"⚠️ No recipes found for '{search_query}'. Try these suggestions: {', '.join(suggestions[:5])}", "error")
                else:
                    flash(f"⚠️ No recipes found with those ingredients. Try these combinations: {', '.join(suggestions[:5])}", "error")
                return render_template("ingredient_search.html", recipes=[], search_performed=search_performed)

            recipes = []
            seen_recipes = set()  # Track unique recipes
            duplicate_count = 0
            
            for idx, hit in enumerate(data["hits"]):
                if "recipe" not in hit:
                    continue
                    
                recipe = hit["recipe"]
                
                # Check for duplicates using multiple attributes
                if is_duplicate_recipe(recipe, seen_recipes):
                    duplicate_count += 1
                    continue
                
                try:
                    # Extract and clean recipe data
                    recipe_data = {
                        "idx": idx,
                        "name": recipe.get("label", "Unknown Recipe"),
                        "image": recipe.get("image", ""),
                        "recipe_link": recipe.get("url", ""),
                        "diet_type": ", ".join(recipe.get("dietLabels", ["N/A"])),
                        "ingredients": recipe.get("ingredientLines", []),
                        "nutrition": {
                            "calories": int(recipe.get("calories", 0)),
                            "protein": float(recipe.get("totalNutrients", {}).get("PROCNT", {}).get("quantity", 0) or 0),
                            "fat": float(recipe.get("totalNutrients", {}).get("FAT", {}).get("quantity", 0) or 0),
                            "carbohydrates": float(recipe.get("totalNutrients", {}).get("CHOCDF", {}).get("quantity", 0) or 0),
                            "fibers": float(recipe.get("totalNutrients", {}).get("FIBTG", {}).get("quantity", 0) or 0)
                        },
                        "source_name": recipe.get("source", "Unknown Source"),
                        "source_url": recipe.get("url", ""),
                        "cuisine_type": ", ".join(recipe.get("cuisineType", ["N/A"])),
                        "meal_type": ", ".join(recipe.get("mealType", ["N/A"]))
                    }
                    recipes.append(recipe_data)
                except (ValueError, TypeError, KeyError) as e:
                    print(f"Error processing recipe {idx}: {e}")
                    continue

            print(f"Number of unique recipes found: {len(recipes)}")
            if duplicate_count > 0:
                flash(f"ℹ️ {duplicate_count} similar recipes were removed to avoid duplicates.", "info")

            if not recipes:
                flash("⚠️ No valid recipes found matching your search.", "error")
                return render_template("ingredient_search.html", recipes=[], search_performed=search_performed)

            session["ingredient_search_results"] = recipes
            return render_template("ingredient_search.html", recipes=recipes, search_performed=search_performed)

        except requests.exceptions.RequestException as e:
            print(f"Request Exception: {str(e)}")
            flash(f"⚠️ Error connecting to recipe service: {str(e)}", "error")
            return render_template("ingredient_search.html", recipes=[], search_performed=search_performed)
        except Exception as e:
            print(f"Unexpected Exception: {str(e)}")
            flash(f"⚠️ An unexpected error occurred: {str(e)}", "error")
            return render_template("ingredient_search.html", recipes=[], search_performed=search_performed)

    return render_template("ingredient_search.html", recipes=[], search_performed=search_performed)

# Recipe Search by Nutrition

@app.route("/nutrition_search", methods=["GET", "POST"])
def nutrition_search():
    search_performed = False

    if request.method == "POST":
        search_performed = True

        def get_value(field, default):
            value = request.form.get(field)
            try:
                return float(value) if value and value.strip() else default
            except ValueError:
                print(f"Invalid value for {field}: {value}")
                return default

        # Get and validate nutrition ranges
        min_calories = get_value("min_calories", 0)
        max_calories = get_value("max_calories", float('inf'))
        min_protein = get_value("min_protein", 0)
        max_protein = get_value("max_protein", float('inf'))
        min_fat = get_value("min_fat", 0)
        max_fat = get_value("max_fat", float('inf'))
        min_carbs = get_value("min_carbs", 0)
        max_carbs = get_value("max_carbs", float('inf'))
        min_fibers = get_value("min_fibers", 0)
        max_fibers = get_value("max_fibers", float('inf'))

        # Validate ranges
        if min_calories > max_calories:
            flash("⚠️ Minimum calories cannot be greater than maximum calories", "error")
            return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)
        if min_protein > max_protein:
            flash("⚠️ Minimum protein cannot be greater than maximum protein", "error")
            return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)
        if min_fat > max_fat:
            flash("⚠️ Minimum fat cannot be greater than maximum fat", "error")
            return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)
        if min_carbs > max_carbs:
            flash("⚠️ Minimum carbohydrates cannot be greater than maximum carbohydrates", "error")
            return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)
        if min_fibers > max_fibers:
            flash("⚠️ Minimum fiber cannot be greater than maximum fiber", "error")
            return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)

        # Get and validate search query
        query = request.form.get("query", "").strip()
        
        # If no query is provided, use a default search term that will return a variety of recipes
        if not query:
            query = "healthy"  # Default search term that will return a good variety of recipes
            flash("ℹ️ No search term provided. Showing a variety of recipes matching your nutritional criteria.", "info")

        print(f"Search Query: {query}")
        print(f"Nutrition Ranges:")
        print(f"Calories: {min_calories}-{max_calories}")
        print(f"Protein: {min_protein}-{max_protein}g")
        print(f"Fat: {min_fat}-{max_fat}g")
        print(f"Carbs: {min_carbs}-{max_carbs}g")
        print(f"Fiber: {min_fibers}-{max_fibers}g")

        # Build API URL with nutrition parameters
        api_url = f"https://api.edamam.com/api/recipes/v2?q={query}&app_id={app_id}&app_key={app_key}&type=public"
        
        # Add nutrition parameters if specified
        if max_calories != float('inf'):
            api_url += f"&calories={min_calories}-{max_calories}"
        if max_protein != float('inf'):
            api_url += f"&nutrients[PROCNT]={min_protein}-{max_protein}"
        if max_fat != float('inf'):
            api_url += f"&nutrients[FAT]={min_fat}-{max_fat}"
        if max_carbs != float('inf'):
            api_url += f"&nutrients[CHOCDF]={min_carbs}-{max_carbs}"
        if max_fibers != float('inf'):
            api_url += f"&nutrients[FIBTG]={min_fibers}-{max_fibers}"

        print(f"API URL: {api_url}")

        try:
            response = requests.get(api_url)
            print(f"Response Status: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            print(f"Response Data: {data.keys() if data else 'No data'}")

            if not data or "hits" not in data or not data["hits"]:
                # Provide helpful suggestions based on the search criteria
                suggestions = []
                if query != "healthy":
                    suggestions.append(f"Try searching for '{query}' with less restrictive nutrition ranges")
                if min_calories > 0 or max_calories < float('inf'):
                    suggestions.append("Try adjusting the calorie range")
                if min_protein > 0 or max_protein < float('inf'):
                    suggestions.append("Try adjusting the protein range")
                if min_fat > 0 or max_fat < float('inf'):
                    suggestions.append("Try adjusting the fat range")
                
                flash(f"⚠️ No recipes found matching your criteria. {' '.join(suggestions)}", "error")
                return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)

            recipes = []
            seen_recipes = set()  # Track unique recipes
            
            for idx, hit in enumerate(data["hits"]):
                if "recipe" not in hit:
                    continue

                recipe = hit["recipe"]
                
                # Check for duplicates using multiple attributes
                if is_duplicate_recipe(recipe, seen_recipes):
                    continue
                
                try:
                    nutrition = {
                        "calories": float(recipe.get("calories", 0)),
                        "protein": float(recipe.get("totalNutrients", {}).get("PROCNT", {}).get("quantity", 0) or 0),
                        "fat": float(recipe.get("totalNutrients", {}).get("FAT", {}).get("quantity", 0) or 0),
                        "carbohydrates": float(recipe.get("totalNutrients", {}).get("CHOCDF", {}).get("quantity", 0) or 0),
                        "fibers": float(recipe.get("totalNutrients", {}).get("FIBTG", {}).get("quantity", 0) or 0)
                    }

                    # Additional validation of nutrition values
                    if (
                        min_calories <= nutrition["calories"] <= max_calories and
                        min_protein <= nutrition["protein"] <= max_protein and
                        min_fat <= nutrition["fat"] <= max_fat and
                        min_carbs <= nutrition["carbohydrates"] <= max_carbs and
                        min_fibers <= nutrition["fibers"] <= max_fibers
                    ):
                        recipes.append({
                            "idx": idx,
                            "name": recipe.get("label", "Unknown Recipe"),
                            "image": recipe.get("image", ""),
                            "recipe_link": recipe.get("url", ""),
                            "diet_type": ", ".join(recipe.get("dietLabels", ["N/A"])),
                            "ingredients": recipe.get("ingredientLines", []),
                            "nutrition": nutrition,
                            "cuisine_type": ", ".join(recipe.get("cuisineType", ["N/A"])),
                            "meal_type": ", ".join(recipe.get("mealType", ["N/A"]))
                        })
                except (ValueError, TypeError, KeyError) as e:
                    print(f"Error processing recipe {idx}: {e}")
                    continue

            print(f"Number of unique recipes found: {len(recipes)}")

            if not recipes:
                flash("⚠️ No recipes found matching your nutritional criteria. Try adjusting the ranges.", "error")
                return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)

            session["nutrition_search_results"] = recipes
            return render_template("nutrition_search.html", recipes=recipes, search_performed=search_performed)

        except requests.exceptions.RequestException as e:
            print(f"Request Exception: {str(e)}")
            flash(f"⚠️ Error connecting to recipe service: {str(e)}", "error")
            return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)
        except Exception as e:
            print(f"Unexpected Exception: {str(e)}")
            flash(f"⚠️ An unexpected error occurred: {str(e)}", "error")
            return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)

    return render_template("nutrition_search.html", recipes=[], search_performed=search_performed)


#  Save Recipe
@app.route("/save_recipe", methods=["POST"])
def save_recipe():
    if "user_id" not in session:
        flash("⚠️ Please log in to save recipes.", "error")
        return redirect(url_for("login"))

    try:
        recipe_data = request.form.get('recipe_data')
        if not recipe_data:
            flash("⚠️ No recipe data provided.", "error")
            return redirect(url_for("recipe_search"))
            
        recipe = json.loads(recipe_data)
        
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO saved_recipes (
                    user_id, recipe_name, image_url, recipe_url, 
                    diet_type, ingredients, calories, protein, 
                    fat, carbohydrates, fiber
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session["user_id"],
                recipe.get("name", "Unknown Recipe"),
                recipe.get("image", ""),
                recipe.get("recipe_link", ""),
                recipe.get("diet_type", "N/A"),
                json.dumps(recipe.get("ingredients", [])),
                recipe.get("nutrition", {}).get("calories", 0),
                recipe.get("nutrition", {}).get("protein", 0),
                recipe.get("nutrition", {}).get("fat", 0),
                recipe.get("nutrition", {}).get("carbohydrates", 0),
                recipe.get("nutrition", {}).get("fibers", 0)
            ))
        db.close()

        flash("✅ Recipe saved successfully!", "success")
        return redirect(url_for("dashboard"))
    except Exception as e:
        print(f"Error saving recipe: {str(e)}")
        flash("⚠️ Error saving recipe. Please try again.", "error")
        return redirect(url_for("recipe_search"))

# 🔹 YouTube Video Fetch
def get_youtube_video(recipe_name):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": f"{recipe_name} recipe",
        "key": YOUTUBE_API_KEY,
        "type": "video",
        "maxResults": 1
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if data["items"]:
            video_id = data["items"][0]["id"]["videoId"]
            return f"https://www.youtube.com/embed/{video_id}"
    except requests.exceptions.RequestException:
        pass
    return None


#  Recipe Detail View
@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id):
    # Get recipes from session
    recipes = session.get("ingredient_search_results") or session.get("nutrition_search_results")
    
    if not recipes:
        flash("⚠️ No recipe data available. Please perform a search first.", "error")
        return redirect(url_for("recipe_search"))
    
    if not isinstance(recipe_id, int) or recipe_id < 0 or recipe_id >= len(recipes):
        flash("⚠️ Invalid recipe ID.", "error")
        return redirect(url_for("recipe_search"))
    
    try:
        selected_recipe = recipes[recipe_id]
        # Detect allergens
        selected_recipe['allergens'] = detect_allergens(selected_recipe['ingredients'])
        
        # Get user's allergen preferences if logged in
        user_allergens = []
        if 'user_id' in session:
            db = get_db_connection()
            with db.cursor() as cursor:
                cursor.execute("SELECT allergens FROM users WHERE user_id = %s", (session["user_id"],))
                result = cursor.fetchone()
                if result and result[0]:
                    user_allergens = result[0].split(',')
            db.close()
        
        # Check for matches with user's allergens
        if user_allergens:
            matching_allergens = [allergen for allergen in selected_recipe['allergens'] 
                                if allergen.lower() in [a.lower() for a in user_allergens]]
            if matching_allergens:
                flash(f"⚠️ Warning: This recipe contains allergens you're sensitive to: {', '.join(matching_allergens)}", "warning")
        
        youtube_video = get_youtube_video(selected_recipe["name"])
        return render_template("recipe_detail.html", recipe=selected_recipe, youtube_video=youtube_video)
    except Exception as e:
        flash(f"⚠️ Error loading recipe: {str(e)}", "error")
        return redirect(url_for("recipe_search"))

# Saved Recipes View
@app.route("/saved_recipes")
def saved_recipes():
    if "user_id" not in session:
        flash("⚠️ Please log in to view saved recipes.", "error")
        return redirect(url_for("login"))

    db = get_db_connection()
    with db.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT * FROM saved_recipes WHERE user_id = %s", (session["user_id"],))
        recipes = cursor.fetchall()
    db.close()

    return render_template("saved_recipes.html", recipes=recipes)

# Profile Routes
@app.route("/profile")
def profile():
    if "user_id" not in session:
        flash("⚠️ Please log in to view your profile.", "error")
        return redirect(url_for("login"))

    db = get_db_connection()
    with db.cursor(pymysql.cursors.DictCursor) as cursor:
        # Get user information
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (session["user_id"],))
        user = cursor.fetchone()

        # Get saved recipes count
        cursor.execute("SELECT COUNT(*) as count FROM saved_recipes WHERE user_id = %s", (session["user_id"],))
        saved_recipes_count = cursor.fetchone()["count"]

        # Get grocery list count
        cursor.execute("SELECT COUNT(*) as count FROM grocery_lists WHERE user_id = %s", (session["user_id"],))
        grocery_list_count = cursor.fetchone()["count"]

        # Get recent activity
        cursor.execute("""
            (SELECT 'saved_recipe' as type, recipe_name as description, saved_at as time, '📚' as icon
            FROM saved_recipes 
            WHERE user_id = %s)
            UNION ALL
            (SELECT 'grocery_list' as type, 'Generated grocery list' as description, created_at as time, '🛒' as icon
            FROM grocery_lists 
            WHERE user_id = %s)
            ORDER BY time DESC
            LIMIT 5
        """, (session["user_id"], session["user_id"]))
        recent_activity = cursor.fetchall()

    db.close()

    return render_template("profile.html",
                         user=user,
                         saved_recipes_count=saved_recipes_count,
                         grocery_list_count=grocery_list_count,
                         days_active=0,  # Removed days_active calculation since created_at is not available
                         recent_activity=recent_activity)

@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        flash("⚠️ Please log in to update your profile.", "error")
        return redirect(url_for("login"))

    email = request.form.get("email")
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    allergens = request.form.getlist("allergens")  # Get list of selected allergens

    db = get_db_connection()
    with db.cursor() as cursor:
        # Verify current password
        cursor.execute("SELECT password FROM users WHERE user_id = %s", (session["user_id"],))
        user = cursor.fetchone()
        
        if not check_password_hash(user[0], current_password):
            flash("⚠️ Current password is incorrect.", "error")
            return redirect(url_for("profile"))

        # Update email if changed
        if email:
            cursor.execute("UPDATE users SET email = %s WHERE user_id = %s", (email, session["user_id"]))

        # Update password if provided
        if new_password:
            if new_password != confirm_password:
                flash("⚠️ New passwords do not match.", "error")
                return redirect(url_for("profile"))
            
            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (hashed_password, session["user_id"]))

        # Update allergens
        allergens_str = ','.join(allergens) if allergens else None
        cursor.execute("UPDATE users SET allergens = %s WHERE user_id = %s", (allergens_str, session["user_id"]))

    db.close()
    flash("✅ Profile updated successfully!", "success")
    return redirect(url_for("profile"))

# Grocery List Routes
@app.route('/grocery_list')
def grocery_list():
    grocery_recipes = session.get('grocery_recipes', [])
    return render_template('grocery_list.html', grocery_recipes=grocery_recipes)

@app.route('/add_to_grocery_list', methods=['POST'])
def add_to_grocery_list():
    try:
        recipe_id = request.form.get('recipe_id')
        if not recipe_id:
            flash("⚠️ No recipe selected", "error")
            return redirect(url_for("recipe_search"))
        
        recipe_id = int(recipe_id)
        recipes = session.get("ingredient_search_results") or session.get("nutrition_search_results")
        
        if not recipes:
            flash("⚠️ No recipe data available", "error")
            return redirect(url_for("recipe_search"))
            
        if recipe_id < 0 or recipe_id >= len(recipes):
            flash("⚠️ Invalid recipe ID", "error")
            return redirect(url_for("recipe_search"))
            
        recipe = recipes[recipe_id]
        
        # Initialize grocery_recipes in session if it doesn't exist
        if 'grocery_recipes' not in session:
            session['grocery_recipes'] = []
            
        # Check if recipe is already in the list
        if any(r.get('idx') == recipe_id for r in session['grocery_recipes']):
            flash("ℹ️ Recipe is already in your grocery list", "info")
            return redirect(url_for("recipe_search"))
        
        # Add recipe to grocery list with ingredients
        session['grocery_recipes'].append({
            'idx': recipe_id,
            'name': recipe.get('name', 'Unknown Recipe'),
            'ingredients': recipe.get('ingredients', [])
        })
        
        flash("✅ Recipe added to grocery list", "success")
        
    except ValueError:
        flash("⚠️ Invalid recipe data", "error")
    except Exception as e:
        print(f"Error adding to grocery list: {str(e)}")
        flash("⚠️ An error occurred while adding the recipe", "error")
    
    return redirect(url_for("recipe_search"))

@app.route('/remove_from_grocery_list', methods=['POST'])
def remove_from_grocery_list():
    recipe_id = request.form.get('recipe_id')
    if not recipe_id:
        flash('No recipe selected', 'error')
        return redirect(url_for('grocery_list'))
    
    try:
        recipe_id = int(recipe_id)
        grocery_recipes = session.get('grocery_recipes', [])
        grocery_recipes = [recipe for recipe in grocery_recipes if recipe['idx'] != recipe_id]
        session['grocery_recipes'] = grocery_recipes
        flash('Recipe removed from grocery list', 'success')
    except ValueError:
        flash('Invalid recipe ID', 'error')
    
    return redirect(url_for('grocery_list'))

@app.route('/clear_grocery_list', methods=['POST'])
def clear_grocery_list():
    session.pop('grocery_recipes', None)
    flash("✅ Grocery list cleared", "success")
    return redirect(url_for("recipe_search"))

@app.route('/generate_grocery_list', methods=['GET', 'POST'])
def generate_grocery_list():
    grocery_recipes = session.get('grocery_recipes', [])
    if not grocery_recipes:
        flash('⚠️ No recipes in grocery list', 'error')
        return redirect(url_for('recipe_search'))
    
    # Combine and categorize ingredients
    all_ingredients = []
    for recipe in grocery_recipes:
        for ingredient in recipe['ingredients']:
            # Clean and standardize ingredient text
            ingredient_text = ingredient.lower().strip()
            
            # Remove common measurements and quantities
            ingredient_text = re.sub(r'\d+\s*(g|kg|ml|l|oz|lb|cup|tbsp|tsp|piece|pieces|slice|slices|pinch|dash|to taste)', '', ingredient_text)
            ingredient_text = re.sub(r'\(.*?\)', '', ingredient_text)  # Remove parenthetical notes
            ingredient_text = re.sub(r'fresh|dried|ground|minced|chopped|sliced|diced|grated|shredded', '', ingredient_text)  # Remove common preparation terms
            ingredient_text = re.sub(r'\s+', ' ', ingredient_text)  # Remove extra spaces
            ingredient_text = ingredient_text.strip()
            
            if ingredient_text:  # Only add non-empty ingredients
                all_ingredients.append({
                    'name': ingredient_text,
                    'original': ingredient,  # Keep original text for reference
                    'recipe': recipe['name']  # Track which recipe it came from
                })
    
    # Group ingredients by category
    categorized_ingredients = {}
    for ingredient in all_ingredients:
        category = categorize_ingredient(ingredient['name'])
        if category not in categorized_ingredients:
            categorized_ingredients[category] = []
        categorized_ingredients[category].append(ingredient)
    
    # Sort categories alphabetically
    categorized_ingredients = dict(sorted(categorized_ingredients.items()))
    
    # Sort ingredients within each category
    for category in categorized_ingredients:
        # Sort by name, then by recipe
        categorized_ingredients[category].sort(key=lambda x: (x['name'], x['recipe']))
        
        # Remove duplicates while keeping the first occurrence
        seen = set()
        unique_ingredients = []
        for ingredient in categorized_ingredients[category]:
            if ingredient['name'] not in seen:
                seen.add(ingredient['name'])
                unique_ingredients.append(ingredient)
        categorized_ingredients[category] = unique_ingredients
    
    # Calculate total number of ingredients
    total_ingredients = sum(len(ingredients) for ingredients in categorized_ingredients.values())
    
    # Add summary information
    summary = {
        'total_recipes': len(grocery_recipes),
        'total_ingredients': total_ingredients,
        'categories': len(categorized_ingredients)
    }
    
    return render_template('generated_list.html',
                         categorized_ingredients=categorized_ingredients,
                         recipes=grocery_recipes,
                         summary=summary)

def categorize_ingredient(ingredient_name):
    # Define ingredient categories and their keywords
    categories = {
        'Produce': [
            'vegetable', 'fruit', 'herb', 'lettuce', 'spinach', 'kale', 'tomato', 'onion', 'garlic',
            'potato', 'carrot', 'celery', 'cucumber', 'pepper', 'mushroom', 'broccoli', 'cauliflower',
            'corn', 'peas', 'bean', 'lentil', 'apple', 'banana', 'orange', 'lemon', 'lime', 'berry',
            'avocado', 'squash', 'zucchini', 'eggplant', 'asparagus', 'artichoke', 'radish', 'turnip',
            'beet', 'cabbage', 'brussels sprout', 'kale', 'arugula', 'watercress', 'endive', 'fennel'
        ],
        'Dairy': [
            'milk', 'cheese', 'yogurt', 'butter', 'cream', 'sour cream', 'cottage cheese', 'ricotta',
            'parmesan', 'mozzarella', 'cheddar', 'feta', 'goat cheese', 'blue cheese', 'gouda', 'brie',
            'cream cheese', 'mascarpone', 'provolone', 'swiss', 'ghee', 'buttermilk', 'half and half'
        ],
        'Meat & Seafood': [
            'beef', 'chicken', 'pork', 'fish', 'shrimp', 'salmon', 'tuna', 'meat', 'lamb', 'turkey',
            'bacon', 'sausage', 'ham', 'steak', 'ground beef', 'chicken breast', 'chicken thigh',
            'cod', 'tilapia', 'halibut', 'mahi mahi', 'trout', 'mackerel', 'sardine', 'anchovy',
            'crab', 'lobster', 'clam', 'mussel', 'oyster', 'scallop', 'calamari', 'octopus'
        ],
        'Pantry': [
            'flour', 'sugar', 'salt', 'pepper', 'oil', 'vinegar', 'spice', 'herb', 'rice', 'pasta',
            'noodle', 'cereal', 'oat', 'quinoa', 'couscous', 'breadcrumb', 'cracker', 'chip',
            'baking powder', 'baking soda', 'yeast', 'cocoa', 'chocolate', 'vanilla', 'cinnamon',
            'nutmeg', 'clove', 'ginger', 'cumin', 'paprika', 'turmeric', 'oregano', 'basil', 'thyme',
            'rosemary', 'sage', 'dill', 'parsley', 'chive', 'mint', 'tarragon', 'marjoram'
        ],
        'Bakery': [
            'bread', 'roll', 'bun', 'pastry', 'cake', 'cookie', 'muffin', 'bagel', 'tortilla',
            'pita', 'naan', 'croissant', 'biscuit', 'scone', 'donut', 'waffle', 'pancake', 'crepe'
        ],
        'Frozen': [
            'frozen', 'ice cream', 'frozen vegetable', 'frozen fruit', 'frozen meal', 'frozen pizza',
            'frozen meat', 'frozen seafood', 'frozen dessert', 'frozen juice', 'frozen yogurt'
        ],
        'Canned Goods': [
            'canned', 'jar', 'preserved', 'sauce', 'soup', 'broth', 'stock', 'canned vegetable',
            'canned fruit', 'canned meat', 'canned fish', 'canned bean', 'canned tomato',
            'canned corn', 'canned mushroom', 'canned soup', 'canned broth', 'canned sauce'
        ],
        'Beverages': [
            'water', 'juice', 'soda', 'coffee', 'tea', 'wine', 'beer', 'milk', 'almond milk',
            'soy milk', 'coconut milk', 'oat milk', 'rice milk', 'lemonade', 'iced tea',
            'sports drink', 'energy drink', 'sparkling water', 'mineral water'
        ],
        'Snacks': [
            'chip', 'cracker', 'nut', 'snack', 'popcorn', 'pretzel', 'granola', 'trail mix',
            'dried fruit', 'jerky', 'beef jerky', 'fruit snack', 'cereal bar', 'protein bar',
            'energy bar', 'candy', 'chocolate', 'gum', 'mint'
        ],
        'Other': []  # Default category
    }
    
    ingredient_name = ingredient_name.lower()
    
    # Check each category's keywords
    for category, keywords in categories.items():
        if any(keyword in ingredient_name for keyword in keywords):
            return category
    
    return 'Other'

@app.route('/download_grocery_list')
def download_grocery_list():
    grocery_recipes = session.get('grocery_recipes', [])
    if not grocery_recipes:
        flash('No recipes in grocery list', 'error')
        return redirect(url_for('grocery_list'))
    
    # Create a BytesIO buffer to store the PDF
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    category_style = ParagraphStyle(
        'CategoryStyle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#0B4B57'),
        spaceAfter=12,
        spaceBefore=20
    )
    
    # Create the content list
    content = []
    
    # Add title
    content.append(Paragraph("🛒 Grocery List", title_style))
    content.append(Spacer(1, 20))
    
    # Add recipes summary
    content.append(Paragraph("Recipes Included:", styles['Heading3']))
    for recipe in grocery_recipes:
        content.append(Paragraph(f"• {recipe['name']}", styles['Normal']))
    content.append(Spacer(1, 20))
    
    # Combine and categorize ingredients
    all_ingredients = []
    for recipe in grocery_recipes:
        for ingredient in recipe['ingredients']:
            # Clean and standardize ingredient text
            ingredient_text = ingredient.lower().strip()
            
            # Remove common measurements and quantities
            ingredient_text = re.sub(r'\d+\s*(g|kg|ml|l|oz|lb|cup|tbsp|tsp|piece|pieces|slice|slices|pinch|dash|to taste)', '', ingredient_text)
            ingredient_text = re.sub(r'\(.*?\)', '', ingredient_text)  # Remove parenthetical notes
            ingredient_text = re.sub(r'fresh|dried|ground|minced|chopped|sliced|diced|grated|shredded', '', ingredient_text)  # Remove common preparation terms
            ingredient_text = re.sub(r'\s+', ' ', ingredient_text)  # Remove extra spaces
            ingredient_text = ingredient_text.strip()
            
            if ingredient_text:  # Only add non-empty ingredients
                all_ingredients.append({
                    'name': ingredient_text,
                    'original': ingredient,
                    'recipe': recipe['name']
                })
    
    # Group ingredients by category
    categorized_ingredients = {}
    for ingredient in all_ingredients:
        category = categorize_ingredient(ingredient['name'])
        if category not in categorized_ingredients:
            categorized_ingredients[category] = []
        categorized_ingredients[category].append(ingredient)
    
    # Sort categories alphabetically
    categorized_ingredients = dict(sorted(categorized_ingredients.items()))
    
    # Sort ingredients within each category and remove duplicates
    for category in categorized_ingredients:
        # Sort by name, then by recipe
        categorized_ingredients[category].sort(key=lambda x: (x['name'], x['recipe']))
        
        # Remove duplicates while keeping the first occurrence
        seen = set()
        unique_ingredients = []
        for ingredient in categorized_ingredients[category]:
            if ingredient['name'] not in seen:
                seen.add(ingredient['name'])
                unique_ingredients.append(ingredient)
        categorized_ingredients[category] = unique_ingredients
    
    # Add categorized ingredients to content
    for category, ingredients in categorized_ingredients.items():
        content.append(Paragraph(f"📋 {category}", category_style))
        
        # Create a table for ingredients
        data = [[Paragraph("□", styles['Normal']), Paragraph(ingredient['original'], styles['Normal'])] 
                for ingredient in ingredients]
        
        # Create the table
        table = Table(data, colWidths=[0.5*inch, 6*inch])
        
        # Add table style
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        content.append(table)
        content.append(Spacer(1, 10))
    
    # Build the PDF
    doc.build(content)
    
    # Get the value of the BytesIO buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Create response with PDF
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=grocery_list.pdf'
    
    return response

# 🔹 Nutrition API
@app.route('/api/nutrition')
def api_nutrition():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    period = request.args.get('period', 'daily')  # small correction here too!

    db = get_db_connection()
    with db.cursor(pymysql.cursors.DictCursor) as cursor:
        if period == 'monthly':
            cursor.execute(""" 
                SELECT 
                    SUM(CAST(calories AS DECIMAL)) AS calories, 
                    SUM(CAST(protein AS DECIMAL)) AS protein, 
                    SUM(CAST(fat AS DECIMAL)) AS fat, 
                    SUM(CAST(carbohydrates AS DECIMAL)) AS carbohydrates,
                    SUM(CAST(fiber AS DECIMAL)) AS fiber
                FROM saved_recipes 
                WHERE user_id = %s AND saved_at >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
            """, (session['user_id'],))
        else:
            cursor.execute(""" 
                SELECT 
                    SUM(CAST(calories AS DECIMAL)) AS calories, 
                    SUM(CAST(protein AS DECIMAL)) AS protein, 
                    SUM(CAST(fat AS DECIMAL)) AS fat, 
                    SUM(CAST(carbohydrates AS DECIMAL)) AS carbohydrates,
                    SUM(CAST(fiber AS DECIMAL)) AS fiber
                FROM saved_recipes 
                WHERE user_id = %s AND DATE(saved_at) = CURDATE()
            """, (session['user_id'],))

        result = cursor.fetchone()
    db.close()

    # Safely handle if any value is None
    calories = float(result.get("calories") or 0)
    protein = float(result.get("protein") or 0)
    fat = float(result.get("fat") or 0)
    carbohydrates = float(result.get("carbohydrates") or 0)
    fiber = float(result.get("fiber") or 0)

    return jsonify({
        "calories": calories,
        "protein": protein,
        "fat": fat,
        "carbohydrates": carbohydrates,
        "fiber": fiber
    })

# 🔹 Meal History API
@app.route("/api/meal-history")
def meal_history():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    period = request.args.get('period', 'daily')
    db = get_db_connection()

    with db.cursor(pymysql.cursors.DictCursor) as cursor:
        if period == 'monthly':
            cursor.execute("""
                SELECT recipe_name, calories, saved_at
                FROM saved_recipes
                WHERE user_id = %s AND saved_at >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
                ORDER BY saved_at DESC
            """, (session["user_id"],))
        else:
            cursor.execute("""
                SELECT recipe_name, calories, saved_at
                FROM saved_recipes
                WHERE user_id = %s AND DATE(saved_at) = CURDATE()
                ORDER BY saved_at DESC
            """, (session["user_id"],))

        recipes = cursor.fetchall()

    db.close()
    return jsonify({"recipes": recipes})

# 🔹 Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("✅ You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/nutrition_monitor")
def nutrition_monitor():
    if "user_id" not in session:
        flash("⚠️ Please log in to view nutrition data.", "error")
        return redirect(url_for("login"))

    period = request.args.get('period', 'daily')  # Get period from query params
    
    db = get_db_connection()
    with db.cursor(pymysql.cursors.DictCursor) as cursor:
        if period == 'monthly':
            # Get last 30 days of nutrition data
            cursor.execute("""
                SELECT 
                    DATE(saved_at) as date,
                    SUM(CAST(calories AS DECIMAL)) as total_calories,
                    SUM(CAST(protein AS DECIMAL)) as total_protein,
                    SUM(CAST(fat AS DECIMAL)) as total_fat,
                    SUM(CAST(carbohydrates AS DECIMAL)) as total_carbs,
                    SUM(CAST(fiber AS DECIMAL)) as total_fiber
                FROM saved_recipes 
                WHERE user_id = %s 
                AND saved_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY DATE(saved_at)
                ORDER BY date
            """, (session["user_id"],))
        else:
            # Get today's nutrition data
            cursor.execute("""
                SELECT 
                    recipe_name,
                    calories,
                    protein,
                    fat,
                    carbohydrates,
                    fiber,
                    saved_at
                FROM saved_recipes 
                WHERE user_id = %s 
                AND DATE(saved_at) = CURDATE()
                ORDER BY saved_at
            """, (session["user_id"],))
        
        nutrition_data = cursor.fetchall()

        # Calculate totals and averages
        if period == 'monthly':
            totals = {
                'calories': sum(day['total_calories'] for day in nutrition_data),
                'protein': sum(day['total_protein'] for day in nutrition_data),
                'fat': sum(day['total_fat'] for day in nutrition_data),
                'carbs': sum(day['total_carbs'] for day in nutrition_data),
                'fiber': sum(day['total_fiber'] for day in nutrition_data)
            }
            averages = {
                'calories': totals['calories'] / len(nutrition_data) if nutrition_data else 0,
                'protein': totals['protein'] / len(nutrition_data) if nutrition_data else 0,
                'fat': totals['fat'] / len(nutrition_data) if nutrition_data else 0,
                'carbs': totals['carbs'] / len(nutrition_data) if nutrition_data else 0,
                'fiber': totals['fiber'] / len(nutrition_data) if nutrition_data else 0
            }
        else:
            totals = {
                'calories': sum(meal['calories'] for meal in nutrition_data),
                'protein': sum(meal['protein'] for meal in nutrition_data),
                'fat': sum(meal['fat'] for meal in nutrition_data),
                'carbs': sum(meal['carbohydrates'] for meal in nutrition_data),
                'fiber': sum(meal['fiber'] for meal in nutrition_data)
            }
            averages = totals  # For daily view, totals and averages are the same

    db.close()

    return render_template("nutrition_monitor.html",
                         nutrition_data=nutrition_data,
                         totals=totals,
                         averages=averages,
                         period=period)

# Start Server
if __name__ == "__main__":
    app.run(debug=True)
