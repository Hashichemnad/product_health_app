import os
import requests  # Make sure to install this library
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import google.generativeai as genai

app = Flask(__name__)

# Configure your database URI here
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///products.db'
db = SQLAlchemy(app)


# Database model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    ingredients = db.Column(db.PickleType)  # Store array of ingredients
    nutrient_facts = db.Column(db.PickleType)  # Store array of nutrient facts
    health_rating = db.Column(db.Float)  # Rating number (1-10)
    health_rating_stage = db.Column(db.String(100))  # e.g., "Good", "Moderate", "Poor"
    health_rating_comment = db.Column(db.String(500))  # Comment or detailed review

    def __repr__(self):
        return f'<Product {self.name}>'

# Initialize the database
with app.app_context():
    db.create_all()

# Helper function to call Gemini API
def analyze_with_gemini(ingredients, product_name):

    genai.configure(api_key='AIzaSyDv-cc3OcsAjqmaSFtnlOUI3qNY-fd30K8')

    # Create the model
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
    )

    chat_session = model.start_chat(history=[])

    # Prepare input for the model

    input_message = f"""Analyze the product '{product_name}' with ingredients : '{', '.join(ingredients)}'. 
        Please rate the healthiness of the product on a scale of 1-10 based on its ingredients. provide response in the format, first line is health rating only the value, second line is health stage shows one line comment about the product
        and third line with a summarize the main health concerns and impact and any better alternative which shouldnt excess 5 lines."""
   
    response = chat_session.send_message(input_message)
    
    response_lines = response.text.split('\n')
    print(f'RES:  {str(response_lines)}')
    # Extract Health Rating, Stage, and Comments
    health_rating = float(response_lines[0].strip().lstrip('#').strip())  # Extract '5' from '## Health Rating: 5'
    health_stage = response_lines[2].strip()  # Extract the third line for health rating stage
    health_comment = '\n'.join(response_lines[4:]).strip()  # Join the remaining lines for health comments

    return health_rating, health_stage, health_comment

# Route to check if the product exists based on barcode
@app.route('/product/<string:barcode>', methods=['GET'])
def get_product(barcode):
    product = Product.query.filter_by(barcode=barcode).first()
    if product:
        # Return the health rating and details if the product exists
        return jsonify({
            'name': product.name,
            'ingredients': product.ingredients,
            'nutrient_facts': product.nutrient_facts,
            'health_rating': product.health_rating,
            'health_rating_stage': product.health_rating_stage,
            'health_rating_comment': product.health_rating_comment
        })
    else:
        return jsonify({'message': 'Product not found'}), 404

# Route to analyze the product and store in the database
@app.route('/analyze_product', methods=['POST'])
def analyze_product():
    try:
        data = request.json
        product_name = data['name']
        barcode = data['barcode']
        ingredients = data['ingredients']
        nutrient_facts = data.get('nutrient_facts', [])

        # Call Gemini API for health analysis
        health_rating, health_stage, health_comment = analyze_with_gemini(ingredients, product_name)

        # Add product to the database with analysis
        new_product = Product(
            name=product_name,
            barcode=barcode,
            ingredients=ingredients,
            nutrient_facts=nutrient_facts,
            health_rating=health_rating,
            health_rating_stage=health_stage,
            health_rating_comment=health_comment
        )
        db.session.add(new_product)
        db.session.commit()

        # Return the analyzed product details
        return jsonify({
            'name': product_name,
            'barcode': barcode,
            'ingredients': ingredients,
            'nutrient_facts': nutrient_facts,
            'health_rating': health_rating,
            'health_rating_stage': health_stage,
            'health_rating_comment': health_comment
        }), 200

    except Exception as e:
        print(f'Error adding product: {str(e)}')
        return jsonify({'error': f'Failed to analyze product: {str(e)}'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
