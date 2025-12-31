#!/usr/bin/env python3
"""
Usability Assessment for opsechat
Evaluates user experience from new user perspective
"""

import os
import sys
import re
from pathlib import Path

def assess_documentation_clarity():
    """Assess documentation from new user perspective"""
    print("\n=== Documentation Clarity Assessment ===")
    
    docs_to_check = [
        ("README.md", "Main documentation"),
        ("EMAIL_QUICKSTART.md", "Email quick start"),
        ("SECURITY.md", "Security guidelines"),
        ("TESTING.md", "Testing instructions")
    ]
    
    scores = {}
    
    for doc_file, description in docs_to_check:
        doc_path = f"/workspace/{doc_file}"
        if os.path.exists(doc_path):
            with open(doc_path, 'r') as f:
                content = f.read()
            
            # Assess documentation quality
            score = assess_doc_quality(content, description)
            scores[doc_file] = score
            print(f"✅ {doc_file}: {score}/10 - {description}")
        else:
            scores[doc_file] = 0
            print(f"❌ {doc_file}: Missing - {description}")
    
    avg_score = sum(scores.values()) / len(scores) if scores else 0
    print(f"\nOverall Documentation Score: {avg_score:.1f}/10")
    
    return avg_score >= 7.0

def assess_doc_quality(content, doc_type):
    """Assess individual document quality"""
    score = 10
    
    # Check for clear structure
    if not re.search(r'^#+\s+', content, re.MULTILINE):
        score -= 2  # No clear headings
    
    # Check for code examples
    if '```' not in content and doc_type in ["Installation guide", "Testing instructions"]:
        score -= 1  # Missing code examples where expected
    
    # Check for step-by-step instructions
    if doc_type == "Installation guide":
        if not re.search(r'^\d+\.|\*|\-', content, re.MULTILINE):
            score -= 2  # No clear steps
    
    # Check length (too short might be incomplete)
    if len(content) < 500 and doc_type != "Security guidelines":
        score -= 1
    
    return max(0, score)

def main():
    """Run usability assessment"""
    print("=== opsechat Usability Assessment ===")
    print("Evaluating from new user perspective\n")
    
    result = assess_documentation_clarity()
    
    if result:
        print("✅ Documentation is clear and helpful for new users")
        return 0
    else:
        print("⚠️  Documentation needs improvement for new users")
        return 1

if __name__ == "__main__":
    sys.exit(main())