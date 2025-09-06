from django.urls import path
from . import views
from finanace.views import RegisterView,DashboardView,TransactionView,TransactionListView,GoalCreateView,export_transaction
urlpatterns=[
    path('register/',RegisterView.as_view(),name="register"),
    path("",DashboardView.as_view(),name="dashboard"),
    path("transaction/add/",TransactionView.as_view(),name="Transaction_add"),
    path("transactions/",TransactionListView.as_view(),name="Transaction_list"),
    path("transactions/goal",GoalCreateView.as_view(),name="Goal"),
    path('generate-report/',export_transaction,name="export_transaction"),
    path('upload-csv/', views.upload_csv, name='upload_csv'),
]