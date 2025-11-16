#!/usr/bin/env python3
"""
PacketFS AWS Lambda Handler
Serverless compute execution for distributed jobs
Deploy: sam deploy or serverless deploy
"""

import json
import time
import logging
import urllib.request
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for PacketFS jobs
    
    Expected event:
    {
        "jobId": "job-12345",
        "program": {
            "op": "counteq",
            "data_url": "https://example.com/data.bin",
            "offset": 0,
            "length": 1048576,
            "imm": 42
        },
        "timeout": 30000
    }
    """
    start_time = time.time()
    
    try:
        logger.info(f"Processing job: {event.get('jobId')}")
        
        # Extract job parameters
        job_id = event.get('jobId', 'unknown')
        program = event.get('program')
        timeout = event.get('timeout', 30000) / 1000  # Convert ms to seconds
        
        if not program or 'op' not in program:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'Missing program or operation',
                    'jobId': job_id
                })
            }
        
        # Fetch data from URL
        data_url = program.get('data_url')
        if not data_url:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': 'Missing data_url',
                    'jobId': job_id
                })
            }
        
        # Download data with optional range
        bytes_data = fetch_data(data_url, program, timeout)
        
        # Execute operation
        result = execute_operation(program, bytes_data)
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        logger.info(f"Job {job_id} completed: {result.get('op')} in {execution_time_ms:.1f}ms")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'jobId': job_id,
                'results': result,
                'executionTimeMs': execution_time_ms,
                'bytesProcessed': len(bytes_data),
                'region': context.invoked_function_arn.split(':')[3],
                'memoryUsed': context.memory_limit_in_mb
            })
        }
        
    except Exception as e:
        execution_time_ms = (time.time() - start_time) * 1000
        logger.error(f"Job processing failed: {str(e)}", exc_info=True)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'jobId': event.get('jobId', 'unknown'),
                'executionTimeMs': execution_time_ms
            })
        }


def fetch_data(url: str, program: Dict[str, Any], timeout: float) -> bytes:
    """
    Fetch data from URL with optional Range header
    """
    try:
        headers = {}
        
        # Add Range header if offset/length specified
        if 'offset' in program and 'length' in program:
            offset = program['offset']
            length = program['length']
            end = offset + length - 1
            headers['Range'] = f'bytes={offset}-{end}'
        
        # Create request
        req = urllib.request.Request(url, headers=headers)
        
        # Set timeout
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
            
    except Exception as e:
        logger.error(f"Data fetch failed: {str(e)}")
        raise


def execute_operation(program: Dict[str, Any], data: bytes) -> Dict[str, Any]:
    """
    Execute a PacketFS operation
    """
    op = program.get('op')
    imm = program.get('imm', 0) & 0xFF
    offset = program.get('offset', 0)
    length = program.get('length', len(data))
    
    # Extract slice
    start = offset
    end = min(offset + length, len(data))
    slice_data = data[start:end]
    
    if op == 'counteq':
        count = sum(1 for b in slice_data if b == imm)
        return {
            'op': 'counteq',
            'count': count,
            'bytesScanned': len(slice_data)
        }
    
    elif op == 'crc32c':
        crc = 0xFFFFFFFF
        for byte in slice_data:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
        
        return {
            'op': 'crc32c',
            'checksum': (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF,
            'bytesProcessed': len(slice_data)
        }
    
    elif op == 'fnv64':
        hash_val = 0xcbf29ce484222325
        fnv_prime = 0x100000001b3
        
        for byte in slice_data:
            hash_val ^= byte
            hash_val = (hash_val * fnv_prime) & 0xFFFFFFFFFFFFFFFF
        
        return {
            'op': 'fnv64',
            'hash': hex(hash_val),
            'bytesHashed': len(slice_data)
        }
    
    elif op == 'xor':
        result = 0
        for byte in slice_data:
            result ^= (byte ^ imm)
        
        return {
            'op': 'xor',
            'result': result,
            'bytesProcessed': len(slice_data)
        }
    
    elif op == 'add':
        result = 0
        for byte in slice_data:
            result += (byte + imm) & 0xFF
        
        return {
            'op': 'add',
            'result': result,
            'bytesProcessed': len(slice_data)
        }
    
    else:
        raise ValueError(f'Unknown operation: {op}')


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'jobId': 'test-job-1',
        'program': {
            'op': 'counteq',
            'data_url': 'https://www.w3.org/WAI/WCAG21/Techniques/pdf/pdf-1.pdf',  # Public PDF
            'offset': 0,
            'length': 1024,
            'imm': 0x25  # '%' character
        },
        'timeout': 30000
    }
    
    class MockContext:
        invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:packetfs-compute'
        memory_limit_in_mb = 128
    
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(json.loads(result['body']), indent=2))
