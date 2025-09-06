from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views import View
from finanace.forms import RegisterForm,TransactionForm,GoalForm
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Transaction,Goal
from .admin import TransactionResource
from django.db.models import Sum
from django.contrib import messages
import matplotlib.pyplot as plt
import io
import base64
from .models import Transaction
from django.contrib.auth.decorators import login_required
import calendar
from collections import defaultdict
from datetime import datetime
from matplotlib.ticker import MaxNLocator
import csv
from datetime import datetime
from decimal import Decimal


class RegisterView(View):
    def get(self, request, *args, **kwargs):
        form = RegisterForm()
        return render(request, "register.html", {'form': form})

    def post(self, request, *args, **kwargs):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request,"Account Created successfully")
            return redirect('login')  # <- Use a valid named URL
        return render(request, "register.html", {'form': form})

class DashboardView(LoginRequiredMixin,View):
    def get(self,request,*args,**kwargs):
        transaction=Transaction.objects.filter(user=request.user)
        goal=Goal.objects.filter(user=request.user)
        total_income=Transaction.objects.filter(user=request.user,transaction_type="Income").aggregate(Sum('amount'))['amount__sum'] or 0
        total_expense=Transaction.objects.filter(user=request.user,transaction_type="Expense").aggregate(Sum('amount'))['amount__sum'] or 0

        net_saving=total_income-total_expense
        remaining_saving=net_saving
        goal_progress=[]
        for g in goal:
            if remaining_saving>=g.target_amount:
                goal_progress.append({'goal':g,"progress":100})
                remaining_saving-=g.target_amount
            elif remaining_saving>0:
                progress=(remaining_saving/g.target_amount)*100
                goal_progress.append({'goal':g,"progress":progress})
                remaining_saving=0
            else:
                goal_progress.append({'goal':g,"progress":0})


        context={
            'transactions':transaction,
            'total_income':total_income,
            'total_expense':total_expense,
            'net_saving':net_saving,
            'goal_progress':goal_progress
        }

        return render(request,"dashboard.html",context)
    
class TransactionView(LoginRequiredMixin,View):
    
    def get(self,request,*args,**kwargs):
        form=TransactionForm()
        return render(request,"transaction_form.html",{'form':form})
    
    def post(self, request, *args, **kwargs):
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user=request.user
            transaction.save()
            messages.success(request,"Added Transaction")
            return redirect('dashboard')  # <- Use a valid named URL
        
        def __str__(self):
            return self.title
    
class TransactionListView(View):
    def get(self,request,*args,**kwargs):
        transaction=Transaction.objects.filter(user=request.user)
        return render(request,"transaction_list.html",{'transaction':transaction})
    
class GoalCreateView(LoginRequiredMixin,View):
    
    
    def get(self,request,*args,**kwargs):
        form=GoalForm()
        return render(request,"goal_form.html",{'form':form})
    
    def post(self, request, *args, **kwargs):
        form = GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user=request.user
            goal.save()
            messages.success(request,"Added Goal")
            return redirect('dashboard')  # <- Use a valid named URL
        
        def __str__(self):
            return self.title

def export_transaction(request):
    user_transactions=Transaction.objects.filter(user=request.user)
    transaction_resource=TransactionResource()
    dataset=transaction_resource.export(queryset=user_transactions)

    excel_data=dataset.export('xlsx')

    response=HttpResponse(excel_data,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    response['Content-Disposition']='attachment;filename=transaction_report.xlsx'

    return response

def get_graph():
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close()
    return image_base64

@login_required
def graphs_view(request):
    transactions = Transaction.objects.filter(user=request.user)

    if not transactions.exists():
        return render(request, 'graphs.html', {
            'pie_chart': None,
            'bar_chart': None,
            'message': 'No transactions available to display graphs.'
        })
    # Pie chart (Income vs Expense)
    income = sum(t.amount for t in transactions if t.transaction_type == 'Income')
    expense = sum(t.amount for t in transactions if t.transaction_type == 'Expense')
    labels = ['Income', 'Expense']
    values = [income, expense]
    colors = ['#28a745', '#dc3545']

    plt.figure(figsize=(4, 4))
    plt.pie(values, labels=labels, autopct='%1.1f%%', colors=colors)
    plt.title('Income vs Expense')
    pie_chart = get_graph()

    # Bar chart (Monthly Category-wise)
    bar_data = defaultdict(lambda: defaultdict(float))  # {month: {category: amount}}

    for t in transactions:
        month = t.date.strftime('%b')  # Jan, Feb, etc.
        bar_data[month][t.category] += float(t.amount)

    months = list(calendar.month_abbr)[1:]  # ['Jan', 'Feb', ..., 'Dec']
    categories = sorted(set(cat for data in bar_data.values() for cat in data))

    category_totals = {
    cat: [float(bar_data[m].get(cat, 0) or 0) for m in months]
    for cat in categories
    }

    plt.figure(figsize=(10, 5))
    bottom = [0] * len(months)
    for cat in categories:
        values = category_totals[cat]
        plt.bar(months, values, bottom=bottom, label=cat)
        bottom = [bottom[i] + values[i] for i in range(len(values))]

    plt.title('Monthly Category-wise Spending')
    plt.xlabel('Month')
    plt.ylabel('Amount')
    plt.legend()
    # plt.gca().yaxis.set_major_locator(MaxNLocator(integer=True))
    bar_chart = get_graph()



    return render(request, 'graphs.html', {
        'pie_chart': pie_chart,
        'bar_chart': bar_chart,
    })

def import_transactions(file, user):
    decoded_file = file.read().decode('utf-8').splitlines()
    reader = csv.DictReader(decoded_file)

    for row in reader:
        try:
            # Parse date in format '1/1/2022'
            date = datetime.strptime(row['date'], '%Y-%m-%d').date()
            
            # Determine transaction type
            transaction_type = 'Income' if row['DrCr'].strip().lower() == 'cr' else 'Expense'

            # Create Transaction
            Transaction.objects.create(
                user=user,
                title=row['name'],
                amount=row['amount'],
                transaction_type=transaction_type,
                date=date,
                category='Imported'  # or use custom logic here
            )

        except Exception as e:
            print(f"❌ Failed to import row: {row} — Error: {e}")


@login_required
def upload_csv(request):
    if request.method == 'POST' and request.FILES['csv_file']:
        csv_file = request.FILES['csv_file']
        import_transactions(csv_file, request.user)
        return redirect('dashboard')  # or your transaction list view
    
    return render(request, 'upload_bank_statement.html')   