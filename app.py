import streamlit as st
import anthropic
from PIL import Image
import os
from dotenv import load_dotenv
import json
import base64

# ===== CONFIG =====
load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    st.error("⚠️ API Key not found!")
    st.stop()

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DEFAULT_ROOMMATES = [
    "Chandu", "Jaffer", "Lucky", "Indra", "Neeraj",
    "Shyam", "Amrit", "Jai", "Talan", "Chandu Dadi"
]

# ===== FUNCTIONS =====

def image_to_base64(image_file):
    bytes_data = image_file.read()
    return base64.b64encode(bytes_data).decode('utf-8')

def extract_items_from_bill(image_file, filename):
    image_file.seek(0)
    base64_image = image_to_base64(image_file)
    media_type = "image/png" if filename.lower().endswith('.png') else "image/jpeg"
    
    prompt = """Extract ALL items from this grocery bill.
Return ONLY valid JSON:
{
    "store_name": "Store name",
    "date": "2026-01-17",
    "total": 45.80,
    "currency": "EUR",
    "items": [
        {"name": "Bread", "price": 2.40}
    ]
}
Rules: Extract EVERY item, prices in Euros, return ONLY JSON."""
    
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64_image
                    }},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        response_text = message.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        return json.loads(response_text.strip())
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None

def calculate_settlement(bills_data):
    settlement = {rm: {"owes": {}, "net": 0, "details": []} 
                  for rm in DEFAULT_ROOMMATES}
    
    for bill_idx, bill in enumerate(bills_data, 1):
        payer = bill.get('payer')
        if not payer:
            continue
            
        for item_idx, item in enumerate(bill['items'], 1):
            participants = item.get('participants', [])
            if not participants:
                continue
            
            split_amount = round(item['price'] / len(participants), 2)
            
            for participant in participants:
                if participant != payer:
                    if payer not in settlement[participant]["owes"]:
                        settlement[participant]["owes"][payer] = 0
                    settlement[participant]["owes"][payer] += split_amount
                    settlement[participant]["net"] += split_amount
                    settlement[participant]["details"].append({
                        "bill_num": bill_idx,
                        "bill_name": bill['store_name'],
                        "item_num": item_idx,
                        "item_name": item['name'],
                        "amount": split_amount,
                        "payer": payer
                    })
    
    for person in settlement:
        settlement[person]["net"] = round(settlement[person]["net"], 2)
        for payer in settlement[person]["owes"]:
            settlement[person]["owes"][payer] = round(settlement[person]["owes"][payer], 2)
    
    return settlement

# ===== BUTTON CALLBACKS =====

def add_visitor_callback(bill_idx, item_idx):
    """Callback to show visitor input"""
    st.session_state[f"show_visitor_b{bill_idx}_i{item_idx}"] = True

def confirm_visitor_callback(bill_idx, item_idx, visitor_name):
    """Callback to add visitor"""
    if visitor_name and visitor_name.strip():
        visitor = visitor_name.strip()
        if visitor not in st.session_state.bills_data[bill_idx]['items'][item_idx]['participants']:
            st.session_state.bills_data[bill_idx]['items'][item_idx]['participants'].append(visitor)
    st.session_state[f"show_visitor_b{bill_idx}_i{item_idx}"] = False

def cancel_visitor_callback(bill_idx, item_idx):
    """Callback to cancel visitor input"""
    st.session_state[f"show_visitor_b{bill_idx}_i{item_idx}"] = False

# ===== SESSION STATE =====

def init_session_state():
    if 'bills_data' not in st.session_state:
        st.session_state.bills_data = []
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 1

# ===== STEP 1 =====

def show_step1_upload():
    st.title("💰 Bill Splitter Pro")
    st.header("📤 Step 1: Upload Bills")
    
    uploaded_files = st.file_uploader(
        "Choose bill images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="file_uploader"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
        
        cols = st.columns(min(len(uploaded_files), 3))
        for idx, file in enumerate(uploaded_files):
            with cols[idx % 3]:
                image = Image.open(file)
                st.image(image, caption=file.name, use_container_width=True)
        
        if st.button("🔍 Extract Items", type="primary", use_container_width=True):
            with st.spinner("Extracting..."):
                st.session_state.bills_data = []
                
                for file in uploaded_files:
                    bill_data = extract_items_from_bill(file, file.name)
                    if bill_data:
                        for item in bill_data['items']:
                            item['participants'] = []
                        bill_data['payer'] = None
                        bill_data['filename'] = file.name
                        st.session_state.bills_data.append(bill_data)
                
                if st.session_state.bills_data:
                    st.success("✅ Extraction complete!")
                    st.balloons()
                    st.session_state.current_step = 2
                    st.rerun()

# ===== STEP 2 =====

def show_step2_assign():
    st.title("💰 Bill Splitter Pro")
    st.header("✏️ Step 2: Assign Participants")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("← Back", key="back_to_step1"):
            st.session_state.current_step = 1
            st.rerun()
    
    if not st.session_state.bills_data:
        st.warning("No bills found")
        return
    
    # Progress
    total = sum(len(bill['items']) for bill in st.session_state.bills_data)
    assigned = sum(1 for bill in st.session_state.bills_data 
                   for item in bill['items'] if item.get('participants'))
    st.progress(assigned/total if total > 0 else 0, text=f"{assigned}/{total} assigned")
    
    for bill_idx, bill in enumerate(st.session_state.bills_data):
        st.markdown(f"### 🛒 Bill {bill_idx + 1}: {bill['store_name']} (€{bill['total']:.2f})")
        st.markdown("---")
        
        for item_idx, item in enumerate(bill['items']):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Item {item_idx + 1}: {item['name']}**")
            with col2:
                st.markdown(f"**€{item['price']:.2f}**")
            
            if 'participants' not in item:
                item['participants'] = []
            
            # Get all people
            all_people = DEFAULT_ROOMMATES.copy()
            for p in item['participants']:
                if p not in all_people:
                    all_people.append(p)
            
            # Checkboxes
            cols = st.columns(4)
            
            participants_key = f"participants_b{bill_idx}_i{item_idx}"
            if participants_key not in st.session_state:
                st.session_state[participants_key] = item['participants'].copy()
            
            new_participants = []
            for i, person in enumerate(all_people):
                with cols[i % 4]:
                    checked = st.checkbox(
                        person,
                        value=person in st.session_state[participants_key],
                        key=f"cb_b{bill_idx}_i{item_idx}_{person}"
                    )
                    if checked:
                        new_participants.append(person)
            
            item['participants'] = new_participants
            st.session_state[participants_key] = new_participants
            
            st.markdown("")
            
            # Only Visitor button
            btn_cols = st.columns([1, 3])
            
            with btn_cols[0]:
                st.button(
                    "+ Visitor",
                    key=f"btn_vis_b{bill_idx}_i{item_idx}",
                    on_click=add_visitor_callback,
                    args=(bill_idx, item_idx)
                )
            
            # Visitor input
            visitor_show_key = f"show_visitor_b{bill_idx}_i{item_idx}"
            if st.session_state.get(visitor_show_key, False):
                v1, v2, v3 = st.columns([2, 1, 1])
                
                visitor_input_key = f"visitor_input_b{bill_idx}_i{item_idx}"
                
                with v1:
                    visitor_name = st.text_input(
                        "Name:",
                        key=visitor_input_key,
                        placeholder="Enter visitor name"
                    )
                with v2:
                    st.button(
                        "Add",
                        key=f"btn_add_vis_b{bill_idx}_i{item_idx}",
                        on_click=confirm_visitor_callback,
                        args=(bill_idx, item_idx, visitor_name)
                    )
                with v3:
                    st.button(
                        "Cancel",
                        key=f"btn_cancel_vis_b{bill_idx}_i{item_idx}",
                        on_click=cancel_visitor_callback,
                        args=(bill_idx, item_idx)
                    )
            
            # Show split WITH ITEM DETAILS
            if item['participants']:
                split = item['price'] / len(item['participants'])
                people_list = ", ".join(item['participants'])
                st.info(f"💶 €{split:.2f} per person | Shared by: {people_list}")
            else:
                st.warning("⚠️ No one selected")
            
            st.markdown("---")
    
    # Continue button
    if assigned == total:
        if st.button("Continue →", type="primary", use_container_width=True):
            st.session_state.current_step = 3
            st.rerun()
    else:
        st.warning(f"⚠️ {total - assigned} items remaining")

# ===== STEP 3 =====

def show_step3_payers():
    st.title("💰 Bill Splitter Pro")
    st.header("💳 Step 3: Select Payers")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("← Back", key="back_to_step2"):
            st.session_state.current_step = 2
            st.rerun()
    
    for bill_idx, bill in enumerate(st.session_state.bills_data):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"### Bill {bill_idx + 1}: {bill['store_name']}")
            st.markdown(f"Total: €{bill['total']:.2f}")
        with col2:
            current_payer = bill.get('payer')
            index = 0
            if current_payer in DEFAULT_ROOMMATES:
                index = DEFAULT_ROOMMATES.index(current_payer) + 1
            
            payer = st.selectbox(
                "Paid by:",
                options=["Select..."] + DEFAULT_ROOMMATES,
                index=index,
                key=f"payer_select_{bill_idx}"
            )
            if payer != "Select...":
                bill['payer'] = payer
        st.markdown("---")
    
    all_selected = all(bill.get('payer') for bill in st.session_state.bills_data)
    
    if all_selected:
        if st.button("Calculate →", type="primary", use_container_width=True):
            st.session_state.current_step = 4
            st.rerun()
    else:
        st.warning("⚠️ Select payer for all bills")

# ===== STEP 4 =====

def show_step4_settlement():
    st.title("💰 Bill Splitter Pro")
    st.header("📊 Step 4: Settlement Summary")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("← Back", key="back_to_step3"):
            st.session_state.current_step = 3
            st.rerun()
    
    settlement = calculate_settlement(st.session_state.bills_data)
    grand_total = sum(bill['total'] for bill in st.session_state.bills_data)
    
    # Display overall total
    st.metric("Total Amount", f"€{grand_total:.2f}")
    st.markdown("---")
    
    # ===== DETAILED GROUP SUMMARY =====
    st.subheader("📱 Detailed Group Summary (Copy & Send to WhatsApp)")
    
    # Generate detailed group summary
    group_summary = "💰 BILL SETTLEMENT SUMMARY\n"
    group_summary += "="*50 + "\n\n"
    
    # Add bill details
    group_summary += "📋 BILLS:\n"
    for bill_idx, bill in enumerate(st.session_state.bills_data, 1):
        group_summary += f"Bill {bill_idx}: {bill['store_name']}\n"
        group_summary += f"Total: €{bill['total']:.2f} | Paid by: {bill.get('payer', 'Unknown')}\n\n"
    
    group_summary += f"GRAND TOTAL: €{grand_total:.2f}\n"
    group_summary += "="*50 + "\n\n"
    
    # Add detailed breakdown for each person
    group_summary += "💸 DETAILED SETTLEMENT:\n\n"
    
    for person in DEFAULT_ROOMMATES:
        if settlement[person]["net"] > 0:
            group_summary += f"{'='*50}\n"
            group_summary += f"{person} owes: €{settlement[person]['net']:.2f}\n"
            group_summary += f"{'='*50}\n\n"
            
            for payer, amount in settlement[person]["owes"].items():
                group_summary += f"→ Pays {payer}: €{amount:.2f}\n"
                
                # Get items for this payer
                items = [d for d in settlement[person]["details"] if d["payer"] == payer]
                group_summary += f"  Items ({len(items)}):\n"
                
                for d in items:
                    group_summary += f"  • {d['item_name']} - €{d['amount']:.2f}\n"
                    group_summary += f"    (Bill {d['bill_num']}: {d['bill_name']}, Item #{d['item_num']})\n"
                
                group_summary += "\n"
            
            group_summary += "\n"
    
    group_summary += "="*50 + "\n"
    group_summary += "Please add your amounts to Splitwise\n"
    
    # Display in copyable text box
    st.text_area(
        "📋 Copy this entire detailed summary for the group:",
        value=group_summary,
        height=400,
        key="group_summary"
    )
    
    st.info("👆 Click inside the box above, press Ctrl+A to select all, then Ctrl+C to copy")
    
    st.markdown("---")
    
    # ===== INDIVIDUAL SUMMARIES =====
    st.subheader("👤 Individual Summaries (Optional)")
    
    for person in DEFAULT_ROOMMATES:
        if settlement[person]["net"] > 0:
            with st.expander(f"💸 {person} owes €{settlement[person]['net']:.2f}"):
                
                for payer, amount in settlement[person]["owes"].items():
                    st.markdown(f"**→ Pays {payer}: €{amount:.2f}**")
                    
                    # Get items for this payer
                    items = [d for d in settlement[person]["details"] if d["payer"] == payer]
                    
                    st.markdown(f"**Items included ({len(items)} items):**")
                    for d in items:
                        st.markdown(
                            f"  • **{d['item_name']}** - €{d['amount']:.2f} "
                            f"(Bill {d['bill_num']}: {d['bill_name']}, Item #{d['item_num']})"
                        )
                    st.markdown("")
                
                # Individual copy text
                msg = f"{person} owes:\n\n"
                for payer, amount in settlement[person]["owes"].items():
                    msg += f"→ {payer}: €{amount:.2f}\n"
                    items = [d for d in settlement[person]["details"] if d["payer"] == payer]
                    msg += f"  Items:\n"
                    for d in items:
                        msg += f"  • {d['item_name']} - €{d['amount']:.2f}\n"
                        msg += f"    (Bill {d['bill_num']}: {d['bill_name']}, Item #{d['item_num']})\n"
                    msg += "\n"
                
                st.code(msg, language=None)
    
    st.markdown("---")
    if st.button("🔄 New Session", type="primary", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.current_step = 1
        st.rerun()

# ===== MAIN =====

def main():
    st.set_page_config(
        page_title="Bill Splitter Pro",
        page_icon="💰",
        layout="wide"
    )
    
    init_session_state()
    
    if st.session_state.current_step == 1:
        show_step1_upload()
    elif st.session_state.current_step == 2:
        show_step2_assign()
    elif st.session_state.current_step == 3:
        show_step3_payers()
    elif st.session_state.current_step == 4:
        show_step4_settlement()

if __name__ == "__main__":
    main()
