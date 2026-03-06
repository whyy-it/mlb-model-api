from flask import Flask, request, jsonify
import pickle

app = Flask(__name__)

# Load your trained model
try:
    with open('mlb_model.pkl', 'rb') as f:
        model = pickle.load(f)
    print("✓ Model loaded successfully")
except Exception as e:
    print(f"✗ Error loading model: {e}")
    model = None

@app.route('/', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Model API is running'}), 200

@app.route('/predict', methods=['POST'])
def predict():
    """
    Predict win probabilities for games
    """
    try:
        data = request.get_json()
        
        if not data or 'games' not in data:
            return jsonify({'error': 'Invalid request format'}), 400
        
        games = data['games']
        predictions = []
        
        for game in games:
            # For now, return the probabilities as-is
            pred = {
                'gameId': game.get('gameId'),
                'homeTeam': game.get('homeTeam'),
                'awayTeam': game.get('awayTeam'),
                'homeWinProb': game.get('homeWinProb', 50),
                'awayWinProb': 100 - game.get('homeWinProb', 50),
                'overProb': game.get('overProb', 50)
            }
            predictions.append(pred)
        
        return jsonify({'predictions': predictions}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)