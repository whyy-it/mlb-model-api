from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import numpy as np

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load your trained model
model_data = None
try:
    with open('mlb_model.pkl', 'rb') as f:
        model_data = pickle.load(f)
    print("✓ Model loaded successfully")
    print(f"  - Features: {model_data['feature_cols']}")
    print(f"  - Accuracy: {model_data['accuracy']:.2%}")
except Exception as e:
    print(f"✗ Error loading model: {e}")
    import traceback
    traceback.print_exc()

@app.route('/', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Model API is running'}), 200

@app.route('/predict', methods=['POST', 'OPTIONS'])
def predict():
    """
    Predict home win probability using trained model
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        print("\n" + "="*60)
        print("PREDICTION REQUEST RECEIVED")
        print("="*60)
        
        if model_data is None:
            print("❌ Model not loaded!")
            return jsonify({'error': 'Model not loaded'}), 500
        
        data = request.get_json()
        
        if not data or 'games' not in data:
            print("❌ Invalid request format")
            return jsonify({'error': 'Invalid request format'}), 400
        
        games = data['games']
        print(f"📊 Processing {len(games)} games")
        
        predictions = []
        
        for i, game in enumerate(games):
            try:
                home_team = game.get('homeTeam', 'Unknown')
                away_team = game.get('awayTeam', 'Unknown')
                game_id = game.get('gameId', i)
                
                print(f"\nGame {i+1}: {away_team} @ {home_team}")
                
                # Create simple feature vector
                # Using defaults since we don't have live team stats
                features = [
                    hash(home_team) % 1000 / 1000.0,  # home_team_id
                    hash(away_team) % 1000 / 1000.0,  # away_team_id
                    0.5,                               # is_day_game
                    0.5,                               # game_length_norm
                    0.500,                             # home_win_pct
                    0.500,                             # away_win_pct
                    1.0,                               # home_field_advantage
                    0.4,                               # home_avg_runs
                    0.4,                               # away_avg_runs
                    0.500,                             # home_recent_form
                    0.500,                             # away_recent_form
                ]
                
                print(f"  Features: {features}")
                
                # Scale and predict
                features_scaled = model_data['scaler'].transform([features])
                print(f"  Scaled: {features_scaled[0][:3]}...")
                
                home_win_prob = model_data['model'].predict_proba(features_scaled)[0][1]
                home_win_prob_pct = int(home_win_prob * 100)
                
                print(f"  ✓ Prediction: {home_win_prob_pct}% home win")
                
                pred = {
                    'gameId': game_id,
                    'homeTeam': home_team,
                    'awayTeam': away_team,
                    'homeWinProb': home_win_prob_pct,
                    'awayWinProb': 100 - home_win_prob_pct,
                    'overProb': game.get('overProb', 50)
                }
                
                predictions.append(pred)
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                
                # Fallback to 50%
                predictions.append({
                    'gameId': game.get('gameId'),
                    'homeTeam': game.get('homeTeam'),
                    'awayTeam': game.get('awayTeam'),
                    'homeWinProb': 50,
                    'awayWinProb': 50,
                    'overProb': game.get('overProb', 50)
                })
        
        print(f"\n✓ Returning {len(predictions)} predictions")
        print("="*60 + "\n")
        return jsonify({'predictions': predictions}), 200
    
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
