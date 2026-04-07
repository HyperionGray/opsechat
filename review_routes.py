# Review System Routes
def register_review_routes(
    app,
    id_generator,
    get_random_color,
    add_review,
    get_reviews,
    get_review_stats,
    get_user_review_count_for_session,
):
    """Register review routes with the Flask app"""
    from flask import render_template, jsonify, request, session
    
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
        
        # Get reviews, stats, and session-specific activity
        all_reviews = get_reviews()
        stats = get_review_stats()
        my_review_count = get_user_review_count_for_session(session["_id"])
        
        return render_template("reviews.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              reviews=all_reviews,
                              stats=stats,
                              my_review_count=my_review_count,
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
        my_review_count = get_user_review_count_for_session(session["_id"])
        
        return render_template("reviews.html",
                              hostname=app.config["hostname"],
                              path=app.config["path"],
                              reviews=all_reviews,
                              stats=stats,
                              my_review_count=my_review_count,
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
            review_text = review.get("text", review.get("review_text", ""))
            try:
                rating = int(review.get("rating", 0))
            except (TypeError, ValueError):
                rating = 0
            formatted_reviews.append({
                "id": review["id"],
                "rating": rating,
                "text": review_text,
                "timestamp": review["timestamp"].strftime("%Y-%m-%d %H:%M"),
                "user_id": review["user_id"][:8] + "..."  # Show partial user ID for anonymity
            })
        
        my_review_count = get_user_review_count_for_session(session["_id"]) if "_id" in session else 0
        stats_with_session = dict(stats)
        stats_with_session["my_review_count"] = my_review_count

        return jsonify({
            "reviews": formatted_reviews,
            "stats": stats_with_session,
            "my_review_count": my_review_count
        })


    @app.route('/<string:url_addition>/reviews/me', methods=["GET"])
    def reviews_my_activity(url_addition):
        """Get current session's review activity."""
        if url_addition != app.config["path"]:
            return ('', 404)

        if "_id" not in session:
            return jsonify({
                "success": False,
                "message": "Session not initialized"
            }), 400

        my_review_count = get_user_review_count_for_session(session["_id"])
        return jsonify({
            "success": True,
            "my_review_count": my_review_count
        })