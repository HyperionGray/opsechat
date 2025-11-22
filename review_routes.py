# Review System Routes
@app.route('/<string:url_addition>/reviews', methods=["GET", "POST"])
def reviews_main(url_addition):
    """Main reviews page"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    message = None
    
    if request.method == "POST":
        rating = request.form.get("rating")
        review_text = request.form.get("review_text", "")
        
        if rating and rating.isdigit() and 1 <= int(rating) <= 5:
            review_id = add_review(session["_id"], rating, review_text)
            message = {
                'type': 'success',
                'text': 'Thank you for your review! It has been submitted anonymously.'
            }
        else:
            message = {
                'type': 'error',
                'text': 'Please select a valid rating (1-5 stars).'
            }
    
    # Get reviews and stats
    all_reviews = get_reviews()
    stats = get_review_stats()
    
    return render_template("reviews.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          reviews=all_reviews,
                          stats=stats,
                          message=message,
                          script_enabled=False)


@app.route('/<string:url_addition>/reviews/yesscript', methods=["GET"])
def reviews_script(url_addition):
    """Reviews page with JavaScript enabled"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        session["_id"] = id_generator()
        session["color"] = get_random_color()
    
    all_reviews = get_reviews()
    stats = get_review_stats()
    
    return render_template("reviews.html",
                          hostname=app.config["hostname"],
                          path=app.config["path"],
                          reviews=all_reviews,
                          stats=stats,
                          message=None,
                          script_enabled=True)


@app.route('/<string:url_addition>/reviews/submit', methods=["POST"])
def reviews_submit(url_addition):
    """Submit review via AJAX"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    if "_id" not in session:
        return jsonify({"success": False, "message": "Session expired"})
    
    rating = request.form.get("rating")
    review_text = request.form.get("review_text", "")
    
    if rating and rating.isdigit() and 1 <= int(rating) <= 5:
        review_id = add_review(session["_id"], rating, review_text)
        return jsonify({
            "success": True, 
            "message": "Thank you for your review! It has been submitted anonymously.",
            "review_id": review_id
        })
    else:
        return jsonify({
            "success": False, 
            "message": "Please select a valid rating (1-5 stars)."
        })


@app.route('/<string:url_addition>/reviews/list', methods=["GET"])
def reviews_list_json(url_addition):
    """Get reviews as JSON (for AJAX refresh)"""
    if url_addition != app.config["path"]:
        return ('', 404)
    
    all_reviews = get_reviews()
    stats = get_review_stats()
    
    # Format reviews for JSON response
    formatted_reviews = []
    for review in all_reviews:
        formatted_reviews.append({
            "id": review["id"],
            "rating": review["rating"],
            "text": review["text"],
            "timestamp": review["timestamp"].strftime("%Y-%m-%d %H:%M"),
            "user_id": review["user_id"][:8] + "..."  # Show partial user ID for anonymity
        })
    
    return jsonify({
        "reviews": formatted_reviews,
        "stats": stats
    })