"""
General standalone view functions for session authentication.
"""

from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from ..serializers import UserDetailSerializer
from ..throttles import LoginThrottle


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([LoginThrottle])
def session_login(request):
    """
    Browser login - creates session cookie.
    
    POST /api/login/
    {
        "username": "admin",
        "password": "password123"
    }
    """
    from django.contrib.auth import authenticate, login
    
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Username and password required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(username=username, password=password)
    
    if user and user.is_active:
        login(request, user)  # Creates session cookie
        
        # Use serializer for consistent user data format
        serializer = UserDetailSerializer(user)
        return Response({
            'message': 'Login successful',
            'user': serializer.data
        })
    
    return Response(
        {'error': 'Invalid credentials or inactive account'}, 
        status=status.HTTP_401_UNAUTHORIZED
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def session_logout(request):
    """
    Browser logout - destroys session.
    
    POST /api/logout/
    """
    from django.contrib.auth import logout
    
    logout(request)
    return Response({'message': 'Logout successful'})


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def session_check(request):
    """
    Check if user is authenticated via session.
    
    GET /api/auth/check/
    
    Returns user data if authenticated, otherwise 401 Unauthorized.
    """
    if request.user.is_authenticated:
        # Use serializer for consistent user data format
        serializer = UserDetailSerializer(request.user)
        return Response({
            'authenticated': True,
            'user': serializer.data
        })
    
    return Response(
        {
            'authenticated': False,
            'error': 'Not authenticated'
        },
        status=status.HTTP_401_UNAUTHORIZED
    )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.
    
    GET /api/health/
    
    Checks:
    - Database connectivity
    - Redis connectivity
    
    Returns 200 if healthy, 503 if unhealthy.
    """
    from django.db import connection
    from django.core.cache import cache
    
    health_status = {
        'status': 'healthy',
        'database': 'unknown',
        'redis': 'unknown',
    }
    is_healthy = True
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['database'] = 'ok'
    except Exception as e:
        health_status['database'] = f'error: {str(e)}'
        is_healthy = False
    
    # Check Redis
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            health_status['redis'] = 'ok'
        else:
            health_status['redis'] = 'error: value mismatch'
            is_healthy = False
    except Exception as e:
        health_status['redis'] = f'error: {str(e)}'
        is_healthy = False
    
    if not is_healthy:
        health_status['status'] = 'unhealthy'
        return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    return Response(health_status)
