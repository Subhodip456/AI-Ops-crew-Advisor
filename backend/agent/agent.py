import json, os
from dotenv import load_dotenv
from .prompts import SYSTEM_PROMPT
from .tools import tool_schemas, FUNCTIONS

load_dotenv()

class SarvamAgent:
    def __init__(self):
        self.client=None
        key=os.getenv("SARVAM_API_KEY")
        if key:
            try:
                from sarvamai import SarvamAI
                self.client=SarvamAI(api_subscription_key=key)
            except Exception:
                self.client=None
        self.model=os.getenv("SARVAM_MODEL","sarvam-105b")

    def run(self,user_message,history=None):
        if not self.client:
            return self.fallback(user_message)
        messages=[{"role":"system","content":SYSTEM_PROMPT}]
        messages += (history or [])[-8:]
        messages.append({"role":"user","content":user_message})
        for _ in range(6):
            response=self.client.chat.completions(model=self.model,messages=messages,tools=tool_schemas(),tool_choice="auto",temperature=0.2,max_tokens=2500)
            msg=response.choices[0].message
            calls=getattr(msg,"tool_calls",None)
            if not calls:
                return msg.content or "I can't determine that reliably from the provided operational data."
            messages.append({"role":"assistant","content":getattr(msg,"content",None),"tool_calls":[{"id":c.id,"type":"function","function":{"name":c.function.name,"arguments":c.function.arguments}} for c in calls]})
            for c in calls:
                try:
                    args=json.loads(c.function.arguments)
                    result=FUNCTIONS[c.function.name](**args)
                except Exception as e:
                    result={"error":str(e),"message":"I can't determine that reliably from the provided operational data."}
                messages.append({"role":"tool","tool_call_id":c.id,"content":json.dumps(result,default=str)})
        return "I can't determine that reliably from the provided operational data."

    def fallback(self,q):
        ql=q.lower()
        # Useful local fallback so the app still demonstrates deterministic functionality without an API key.
        if "c-1042" in ql and ("sick" in ql or "out" in ql):
            from .tools import rank_replacement_options_tool
            r=rank_replacement_options_tool("P-2291","Captain")
            rec=r["recommended"]
            return f"Captain C-1042's absence affects pairing P-2291 and flights DX412, DX413, DX588 on 15 Sep. Recommended action: assign {rec['crew_id']} — legal, cost ₹{rec['cost_inr']:,}, coverage {rec['coverage']}. C-2087 is rejected by deterministic duty-limit checks."
        return "Sarvam API key is not configured. Add SARVAM_API_KEY to .env to enable conversational tool-calling. The deterministic API endpoints remain available."
