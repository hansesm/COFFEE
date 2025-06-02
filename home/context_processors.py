# In yourapp/context_processors.py
def add_is_manager(request):
    if request.user.is_authenticated:
        return {"is_manager": request.user.groups.filter(name="manager").exists()}
    return {}
