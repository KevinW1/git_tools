# Git Tools
Just some random tools that make my work easier.


Useful graph view:
```
git config --global alias.graph "log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset%n' --abbrev-commit --date=relative --branches"
```

Git tree view
```
git config --global alias.br '!python ~/code/git_tools/git_tools.py branch tree'
```

    branch_no_upstream
    master
        ├─ test_branch
        │   ├─ fun_branch
        │   └─ test_two
        └─ test_zoo