from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site, RequestSite
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import parsers, renderers, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import list_route
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import UserSerializer, GroupSerializer, ServiceSerializer, ProviderSerializer, \
    ProviderTypeSerializer, ServiceAreaSerializer, APILoginSerializer, APIActivationSerializer
from email_user.forms import EmailUserCreationForm
from email_user.models import EmailUser
from services.models import Service, Provider, ProviderType, ServiceArea


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = EmailUser.objects.all()
    serializer_class = UserSerializer


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class ServiceAreaViewSet(viewsets.ModelViewSet):
    queryset = ServiceArea.objects.all()
    serializer_class = ServiceAreaSerializer


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer


class ProviderTypeViewSet(viewsets.ModelViewSet):
    queryset = ProviderType.objects.all()
    serializer_class = ProviderTypeSerializer


class ProviderViewSet(viewsets.ModelViewSet):
    # This docstring shows up when browsing the API in a web browser:
    """
    Provider view

    In addition to the usual URLs, you can append 'create_provider/' to
    the provider URL and POST to create a new user and provider.

    POST the fields of the provider, except instead of passing the
    user, pass an 'email' and 'password' field so we can create the user
    too.

    The user will be created inactive. An email message will be sent
    to them with a link they'll have to click in order to activate their
    account. After clicking the link, they'll be redirected to the front
    end, logged in and ready to go.
    """

    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer

    @list_route(methods=['post'], permission_classes=[AllowAny])
    def create_provider(self, request, *args, **kwargs):
        """
        Customized "create provider" API call.

        This is distinct from the built-in 'POST to the list URL'
        call because we need it to work for users who are not
        authenticated (otherwise, they can't register).

        Expected data is basically the same as for creating a provider,
        except that in place of the 'user' field, there should be an
        'email' and 'password' field.  They'll be used to create a new user,
        send them an activation email, and create a provider using
        that user.
        """
        if 'email' not in request.data or 'password' not in request.data:
            raise DRFValidationError("Provider create call must provide email and password")

        # Validate the user data
        form = EmailUserCreationForm(data={
            'email': request.data['email'],
            'password1': request.data['password'],
            'password2': request.data['password'],
            })
        if not form.is_valid():
            raise DRFValidationError(form.errors)

        user = get_user_model().objects.create_user(
            email=request.data['email'],
            password=request.data['password'],
            is_active=False
        )
        if Site._meta.installed:
            site = Site.objects.get_current()
        else:
            site = RequestSite(request)
        user.send_activation_email(site, request)

        # Now we have a user, let's just call the built-in create
        # method to create the provider for us. We just need to
        # add the 'user' field to the request data.
        if hasattr(request.data, 'dicts'):
            # This is gross but seems to be necessary for now,
            # becausing just setting an item on the MergeDict
            # appears to be a no-op.
            request.data.dicts[0]['user'] = user.get_api_url()
        else:
            # Maybe we have Django 1.9 and MergeDict is gone :-)
            request.data['user'] = user.get_api_url()
            # Make sure this works though
            assert 'user' in request.data
        return super().create(request, *args, **kwargs)


class APILogin(APIView):
    """
    Allow front-end to pass us an email and a password and get
    back an auth token for the user.

    (Adapted from the corresponding view in DRF for our email-based
    user model.)
    """
    throttle_classes = ()
    permission_classes = ()
    parser_classes = (parsers.FormParser, parsers.MultiPartParser, parsers.JSONParser,)
    renderer_classes = (renderers.JSONRenderer,)

    def post(self, request):
        serializer = APILoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({'token': token.key})


class APIActivationView(APIView):
    """
    Given a user activation key, activate the user and
    return an auth token.
    """
    throttle_classes = ()
    permission_classes = ()
    parser_classes = (parsers.FormParser, parsers.MultiPartParser, parsers.JSONParser,)
    renderer_classes = (renderers.JSONRenderer,)

    def post(self, request):
        serializer = APIActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activation_key = serializer.validated_data['activation_key']

        try:
            user = get_user_model().objects.activate_user(activation_key=activation_key)
        except DjangoValidationError as e:
            raise DRFValidationError(e.messages)

        token, unused = Token.objects.get_or_create(user=user)
        return Response({'token': token.key})
