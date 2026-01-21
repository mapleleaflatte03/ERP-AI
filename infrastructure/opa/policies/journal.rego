# ERPX AI Accounting - OPA Policies
# ==================================
# Open Policy Agent policies for journal entry validation

package erpx.journal

import future.keywords.if
import future.keywords.in
import future.keywords.contains

# Default deny
default allow := false

# Main validation rule
allow if {
    valid_accounts
    balanced_entries
    valid_amounts
    not high_risk
}

# Validate all account codes are in TT200 chart of accounts
valid_accounts if {
    every entry in input.proposal.journal_entries {
        valid_tt200_account(entry.debit_account)
        valid_tt200_account(entry.credit_account)
    }
}

# Check if account is valid TT200 account
valid_tt200_account(code) if {
    code in tt200_accounts
}

# TT200 Chart of Accounts (main accounts)
tt200_accounts := {
    # Loại 1 - Tài sản ngắn hạn
    "111", "1111", "1112", "1113",
    "112", "1121", "1122", "1123",
    "121", "128", "131", "133", "1331", "1332",
    "136", "138", "141", "142",
    "151", "152", "153", "1531", "1532", "1533", "1534",
    "154", "155", "156", "1561", "1562", "1567",
    "157", "158",
    
    # Loại 2 - Tài sản dài hạn
    "211", "2111", "2112", "2113", "2114", "2115", "2118",
    "212", "213", "214", "2141", "2142", "2143", "2147",
    "217", "221", "222", "223", "228", "229",
    "241", "242", "243", "244",
    
    # Loại 3 - Nợ phải trả
    "311", "315", "331", "333", "3331", "33311", "33312",
    "3332", "3333", "3334", "3335", "3336", "3337", "3338", "3339",
    "334", "3341", "3348",
    "335", "336", "337",
    "338", "3381", "3382", "3383", "3384", "3385", "3386", "3387", "3388",
    "341", "343", "344", "347",
    "352", "353", "356", "357",
    
    # Loại 4 - Vốn chủ sở hữu
    "411", "4111", "4112", "4118",
    "412", "413", "414", "417", "418",
    "419", "421", "4211", "4212",
    "441", "461", "466",
    
    # Loại 5 - Doanh thu
    "511", "5111", "5112", "5113", "5114", "5117", "5118",
    "512", "515", "521",
    
    # Loại 6 - Chi phí sản xuất, kinh doanh
    "611", "621", "622", "623",
    "627", "6271", "6272", "6273", "6274", "6277", "6278",
    "631", "632", "635",
    "641", "6411", "6412", "6413", "6414", "6415", "6417", "6418",
    "642", "6421", "6422", "6423", "6424", "6425", "6426", "6427", "6428",
    
    # Loại 7 - Thu nhập khác
    "711",
    
    # Loại 8 - Chi phí khác
    "811", "821", "8211", "8212",
    
    # Loại 9 - Xác định kết quả kinh doanh
    "911"
}

# Check entries are balanced (Total Debit = Total Credit)
balanced_entries if {
    total_debit := sum([entry.debit_amount | entry := input.proposal.journal_entries[_]])
    total_credit := sum([entry.credit_amount | entry := input.proposal.journal_entries[_]])
    abs(total_debit - total_credit) < 1  # Allow 1 VND rounding
}

# Check all amounts are positive
valid_amounts if {
    every entry in input.proposal.journal_entries {
        entry.debit_amount >= 0
        entry.credit_amount >= 0
    }
}

# Check for high risk conditions
high_risk if {
    large_transaction
}

high_risk if {
    sensitive_account_used
}

# Large transaction (over 1 billion VND)
large_transaction if {
    some entry in input.proposal.journal_entries
    entry.debit_amount > 1000000000
}

large_transaction if {
    some entry in input.proposal.journal_entries
    entry.credit_amount > 1000000000
}

# Sensitive accounts that need extra review
sensitive_accounts := {
    "111",  # Tiền mặt
    "411",  # Vốn chủ sở hữu
    "421",  # Lợi nhuận chưa phân phối
    "821",  # Chi phí thuế TNDN
}

sensitive_account_used if {
    some entry in input.proposal.journal_entries
    entry.debit_account in sensitive_accounts
}

sensitive_account_used if {
    some entry in input.proposal.journal_entries
    entry.credit_account in sensitive_accounts
}

# Risk level calculation
risk_level := "high" if {
    high_risk
} else := "medium" if {
    confidence_below_threshold
} else := "low"

# Confidence threshold
confidence_below_threshold if {
    input.proposal.confidence < 0.7
}

# Issues list
issues contains msg if {
    some entry in input.proposal.journal_entries
    not valid_tt200_account(entry.debit_account)
    msg := sprintf("Invalid debit account: %s", [entry.debit_account])
}

issues contains msg if {
    some entry in input.proposal.journal_entries
    not valid_tt200_account(entry.credit_account)
    msg := sprintf("Invalid credit account: %s", [entry.credit_account])
}

issues contains msg if {
    not balanced_entries
    msg := "Journal entries are not balanced (Debit != Credit)"
}

issues contains msg if {
    some entry in input.proposal.journal_entries
    entry.debit_amount < 0
    msg := sprintf("Negative debit amount: %v", [entry.debit_amount])
}

issues contains msg if {
    some entry in input.proposal.journal_entries
    entry.credit_amount < 0
    msg := sprintf("Negative credit amount: %v", [entry.credit_amount])
}

issues contains msg if {
    large_transaction
    msg := "Transaction exceeds 1 billion VND - requires additional review"
}

issues contains msg if {
    sensitive_account_used
    msg := "Transaction involves sensitive accounts - requires additional review"
}

# Absolute value helper
abs(x) := x if {
    x >= 0
}

abs(x) := 0 - x if {
    x < 0
}

# User authorization rules
user_can_approve if {
    input.user_id in approved_users
}

user_can_approve if {
    input.user_role == "accountant"
}

user_can_approve if {
    input.user_role == "manager"
}

approved_users := {"admin", "accountant1", "manager1"}

# Final result
result := {
    "allow": allow,
    "risk_level": risk_level,
    "issues": issues,
    "user_can_approve": user_can_approve
}
