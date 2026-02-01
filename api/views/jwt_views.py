"""
Custom JWT views with throttling.
"""

from rest_framework_simplejwt.views import TokenObtainPairView as BaseTokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from api.throttles import LoginThrottle


class TokenObtainPairView(BaseTokenObtainPairView):
    """JWT token obtain view with rate limiting"""
    throttle_classes = [LoginThrottle]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def jwt_logout(request):
    """
    Logout by blacklisting the refresh token.
    
    Mobile apps should send the refresh_token in request body:
    {
        "refresh": "eyJ0eXAiOiJKV1QiLC..."
    }
    
    After logout, the refresh token can no longer be used to obtain new access tokens.
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Blacklist the refresh token
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response(
            {'message': 'Successfully logged out'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': f'Invalid token: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
