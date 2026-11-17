from django.contrib.auth import views as auth_views
from django.urls import path

from gemach import views as v

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="gemach/login.html"), name="login"),
    path("setup/", v.first_setup, name="first_setup"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", v.dashboard, name="dashboard"),
    path("availability/", v.availability, name="availability"),
    path("board/", v.availability_board, name="board"),
    path("orders/", v.order_list, name="orders"),
    path("orders/new/", v.order_form, name="order_new"),
    path("orders/<int:pk>/", v.order_detail, name="order_detail"),
    path("orders/<int:pk>/edit/", v.order_form, name="order_edit"),
    path("orders/<int:pk>/pickup/", v.order_pickup, name="order_pickup"),
    path("orders/<int:pk>/return/", v.order_return, name="order_return"),
    path("orders/<int:pk>/action/", v.order_action, name="order_action"),
    path("api/customers/", v.customer_lookup, name="customer_lookup"),
    path("api/search/", v.customer_search, name="customer_search"),
    path("api/availability/", v.availability_api, name="availability_api"),
    path("inventory/", v.inventory, name="inventory"),
    path("models/<int:pk>/image/", v.model_image, name="model_image"),
    path("customers/", v.customers, name="customers"),
    path("customers/<int:pk>/", v.customer_detail, name="customer_detail"),
    path("settings/", v.settings_view, name="settings"),
    path("cron/reminders/", v.cron, name="cron"),
    path("healthz", v.healthz, name="healthz"),
]
