from dotenv import load_dotenv
_ = load_dotenv()
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated,List
import operator
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
import os
import re
import subprocess
from tavily import TavilyClient
from langgraph.checkpoint.sqlite import SqliteSaver
from uuid import uuid4
import shutil
from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel
from tavily import TavilyClient
from argparse import ArgumentParser
from prompts import * 

# Create a parser
parser = ArgumentParser(description="Set up environment with API keys.")
# Add arguments for OpenAI and Tavily API keys
parser.add_argument("--openai_key", type=str, required=True, help="API key for OpenAI")
parser.add_argument("--tavily_key", type=str, required=True, help="API key for Tavily")

# Parse the arguments
args = parser.parse_args()

# Set the environment variables with the provided API keys
os.environ['OPENAI_API_KEY'] = args.openai_key
os.environ['TAVILY_API_KEY'] = args.tavily_key

# Initialize the database in memory
memory = SqliteSaver.from_conn_string(":memory:")

# Create a Tavily client instance with the provided API key
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

# Create a ChatOpenAI model instance
model = ChatOpenAI(model="gpt-4-turbo", temperature=0)



class Queries(BaseModel):
    queries: List[str]


def reduce_messages(left: list[AnyMessage], right: list[AnyMessage]) -> list[AnyMessage]:
    # assign ids to messages that don't have them
    for message in right:
        if not message.id:
            message.id = str(uuid4())
    # merge the new messages with the existing messages
    merged = left.copy()
    for message in right:
        for i, existing in enumerate(merged):
            # replace any existing messages with the same id
            if existing.id == message.id:
                merged[i] = message
                break
        else:
            # append any new messages to the end
            merged.append(message)
    return merged


#some utils function to parse and save code and logs
def extract_and_save_cpp_code(text, filename, directory):
    """
    Extracts C++ code enclosed in <cpp_code></cpp_code> tags, formats it using clang-format, 
    and saves it as a .cpp file in the specified directory.
    
    Parameters:
        text (str): Text output from GPT-4 which might include C++ code wrapped in <cpp_code> tags.
        filename (str): Name of the file to save the code, without extension.
        directory (str): Path to the directory where the file will be saved.
    """
    # Extract the C++ code from the text using regular expressions
    pattern = re.compile(r"<cpp_code>(.*?)</cpp_code>", re.DOTALL)
    matches = pattern.search(text)
    if not matches or not matches.group(1).strip():  # Check for no matches or empty code
        print("No C++ code found in the text.")
        return False
    
    cpp_code = matches.group(1).strip()

    # Ensure the directory exists
    os.makedirs(directory, exist_ok=True)
    
    # Full path for the .cpp file
    filepath = os.path.join(directory, f"{filename}.cpp")
    
    # Use clang-format to format the code
    process = subprocess.Popen(['clang-format'], 
                               stdin=subprocess.PIPE, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
    
    # Send the extracted C++ code to clang-format and get the formatted code
    formatted_code, errors = process.communicate(input=cpp_code)
    
    if process.returncode != 0:
        raise Exception(f"clang-format error: {errors}")
    
    # Write the formatted code to the file
    with open(filepath, 'w') as file:
        file.write(formatted_code)
    
    print(f"File saved successfully at {filepath}")
    return True
    
    


def extract_and_save_cmake_code(text, directory):
    """
    Extracts CMake code enclosed in <cmake_code></cmake_code> tags and saves it as a CMakeLists.txt file 
    in the specified directory.
    
    Parameters:
        text (str): Text output which might include CMake configuration code wrapped in <cmake_code> tags.
        directory (str): Path to the directory where the CMakeLists.txt file will be saved.
    """
    # Extract the CMake code from the text using regular expressions
    pattern = re.compile(r"<cmake_code>(.*?)</cmake_code>", re.DOTALL)
    matches = pattern.search(text)
    if not matches or not matches.group(1).strip():  # Check for no matches or empty code
        print("No CMake code found in the text.")
        return False
    
    cmake_code = matches.group(1).strip()

    # Ensure the directory exists
    os.makedirs(directory, exist_ok=True)
    
    # Full path for the CMakeLists.txt file
    filepath = os.path.join(directory, "CMakeLists.txt")
    
    # Write the extracted CMake code to the file
    with open(filepath, 'w') as file:
        file.write(cmake_code)
    
    print(f"CMakeLists.txt file saved successfully at {filepath}")
    return True



def truncate_log_content(file_path, max_length=1000000):
    """ Reads the log file and truncates it to a rough estimate of GPT-4 token limits. """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read(max_length)  # Read only up to max_length characters
    except FileNotFoundError:
        return "Log file not found."

    return content




def run_build_and_application(build_dir, log_file_path, drafts_dir, executable_name = 'inference_env', cmake_path = '/opt/homebrew/bin/cmake', make_path = '/usr/bin/make'):
    # Ensure the build directory exists
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)
    
    # Update main.cpp from the drafts directory
    shutil.copy(os.path.join(drafts_dir, "main.cpp"), os.path.join(build_dir, "main.cpp"))

    # Navigate to the build directory
    os.chdir(build_dir)
    
    # Initialize log content
    log_content = ""
    
    # Run CMake to configure the project
    cmake_command = [cmake_path, ".."]
    cmake_result = subprocess.run(cmake_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log_content += cmake_result.stdout.decode()
    
    # Check if CMake configuration was successful
    if cmake_result.returncode != 0:
        print("CMake configuration failed.")
        with open(log_file_path, 'a') as file:
            file.write(log_content)
        return

    # Build the project with make
    make_command = [make_path]
    make_result = subprocess.run(make_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log_content += make_result.stdout.decode()
    
    # Check if make was successful
    if make_result.returncode != 0:
        print("Build failed.")
        with open(log_file_path, 'a') as file:
            file.write(log_content)
        return

    # Run the compiled executable
    executable_path = os.path.join(build_dir, executable_name)
    runtime_result = subprocess.run([executable_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Check execution status
    if runtime_result.returncode == 0:
        print("Application ran successfully.")
    else:
        print("Application run failed.")
        runtime_log_content = runtime_result.stderr.decode()
        with open(log_file_path, 'a') as file:
            file.write(runtime_log_content)
            
            




class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], reduce_messages]
    task: str
    plan: str
    draft: str
    critique: str
    unit_test_implementation: str
    content : str
    search_content: List[str]
    documentation_content: List[str]
    version_number: int
    max_revisions: int
    debugging_logs: str
    current_unittest: str
    feedback: str
    failing: bool 
    cpp_code_created: bool
    remind_about_cpp_flags: bool

"""
defining the agent nodes below :
"""

def plan_node(state: AgentState):
    
    feedback_content = state['feedback'] # + (state['search_content'])
    search_content = "\n\n".join(state['search_content'] or [])
    if feedback_content != None:
        PROMPT = PLAN_PROMPT + feedback_content + search_content #.format(content=content)
    else:
        PROMPT = PLAN_PROMPT + search_content
    
    messages = [
        SystemMessage(content=PROMPT), 
        HumanMessage(content=state['task']),
        
    ]
    response = model.invoke(messages)
    return {"plan": response.content}


def research_plan_node(state: AgentState):
    queries = model.with_structured_output(Queries).invoke([
        SystemMessage(content=RESEARCH_PLAN_PROMPT),
        HumanMessage(content=state['task'])
    ])
    content = [] #state['documentation_content'] or []
    for q in queries.queries:
        response = tavily.search(query=q, max_results=2)
        for r in response['results']:
            content.append(r['content'])
    return {"search_content": content}



def research_debug_node(state: AgentState):
    queries = model.with_structured_output(Queries).invoke([
        SystemMessage(content=RESEARCH_PLAN_PROMPT),
        HumanMessage(content=state['task'])
    ])
    content = [] #state['debug_search_content'] or []
    for q in queries.queries:
        response = tavily.search(query=q, max_results=2)
        for r in response['results']:
            content.append(r['content'])
    return {"search_content": content}


def generation_node(state: AgentState):
    #content = "\n\n".join(state['feedback'] or [])
    if state['cpp_code_created'] == False:
        reminder = """ATTENTION! ALWAYS REMEMBER: For any C++ code in your provided answer, explicitly wrap the section containing the cpp codewithin:<cpp_code>{your_cpp_code}</cpp_code>"""
        user_message = HumanMessage(content=f"{state['task']}\n\nHere is my plan:\n\n{state['plan']}"+reminder)
    else:
        user_message = HumanMessage(content=f"{state['task']}\n\nHere is my plan:\n\n{state['plan']}")
    messages = [
        SystemMessage(
            content=MAIN_DEVELOPER_PROMPT #.format(content=content)
        ),
        user_message
        ]
    response = model.invoke(messages)
    return {
        "draft": response.content, 
        "revision_number": state.get("revision_number", 1) + 1
    }


def debugger_node(state: AgentState):
    log_file_path = '/Users/nikny/nilsrepo/mmm_sandbox/logs'   # Define the path to your log file
    try:
        # Read and possibly truncate the log file content
        parsed_debugging_logs = truncate_log_content(log_file_path, 1000000)  # Adjust based on token size
        
        messages = [
            SystemMessage(content=DEBUGGER_PROMPT),  # Assuming DEBUGGER_PROMPT is defined elsewhere
            HumanMessage(content=parsed_debugging_logs)
        ]
        response = state.model.invoke(messages)  # Assuming 'state' has a 'model' with an 'invoke' method
        return {"debugging_logs": response.content}
    except Exception as e:
        return {"error": str(e)}
    


"""
pass the draft here, develop unit test, 
upon user-acceptance execute unittest by updating shell script 
with output and execute it in local environment """

def unittest_node(state: AgentState):
    message = [
        
        SystemMessage(content=UNIT_TESTER_PROMPT),
        HumanMessage(content=state['draft'])
        
    ]
    response = model.invoke(message)
    directory = '/Users/nikny/nilsrepo/mmm_sandbox/drafts' 
    is_created = extract_and_save_cpp_code(response.content, 'main', directory)
    # write current unit test to a file using the to cpp function above

    return {"current_unittest": response.content, "cpp_code_created": is_created}



def check_if_cpp_code_created(state: AgentState):
    if state["cpp_code_created"] == True:
        return True #"run_unittest"
    else:
        return False #"main_developer"
     


def feedback_developer_node(state: AgentState):
    messages = [
        SystemMessage(content=FEEDBACK_DEVELOPER_PROMPT), 
        HumanMessage(content=state['draft'])
    ]
    response = model.invoke(messages)
    return {"feedback": response.content}



def run_unittest_node(state: AgentState):
    # Base directory for operations, relative to the current working directory
    base_dir = os.getcwd()
    
    # Define relative paths
    build_dir = os.path.join(base_dir, 'build')
    log_dir = os.path.join(base_dir, 'logs')
    drafts_dir = os.path.join(base_dir, 'drafts')
    
    # Ensure each directory exists
    os.makedirs(build_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(drafts_dir, exist_ok=True)
    
    # Define file paths within the directories
    log_file_path = os.path.join(log_dir, 'build_runtime_logs.txt')
    draft_file_path = os.path.join(drafts_dir, 'main.cpp')
    
    # Run the build and application with the specified directories and files
    run_build_and_application(build_dir, log_file_path, draft_file_path)
    
    return




def research_critique_node(state: AgentState):
    queries = model.with_structured_output(Queries).invoke([
        SystemMessage(content=RESEARCH_CRITIQUE_PROMPT),
        HumanMessage(content=state['critique'])
    ])
    content = state['content'] or []
    for q in queries.queries:
        response = tavily.search(query=q, max_results=2)
        for r in response['results']:
            content.append(r['content'])
    return {"content": content}



def should_continue(state):
    if state["revision_number"] > state["max_revisions"]:
        return END
    return "reflect"


import ipywidgets as widgets
from IPython.display import display

def interactive_failing_check():
    # Define the function that checks if the system is failing
    def check(failing):
        if failing:
            print("unittest failed.")
            state['failing'] = True
            return True
        else:
            print("unittest succeeded")
            state['failing'] = False
            return False

    # Create a checkbox widget for user input
    checkbox = widgets.Checkbox(
        value=False,
        description='did the unittest fail?',
        disabled=False
    )

    # Create a button to submit the value
    button = widgets.Button(description="Check System")

    # Define a function to handle button click, which calls check_if_failing
    def on_button_clicked(b):
        # Call check_if_failing with the current value of the checkbox
        check(checkbox.value)

    # Display the checkbox and button
    display(checkbox, button)

    # Set the button's on-click event to the handler function
    button.on_click(on_button_clicked)


# instantiate the agents graph

builder = StateGraph(AgentState)


builder.add_node("planner", plan_node)
builder.add_node("main_developer", generation_node)
builder.add_node("debugging_developer", debugger_node)
builder.add_node("feedback_developer", feedback_developer_node)
builder.add_node("research_plan", research_plan_node)
builder.add_node("research_debug", research_critique_node)
builder.add_node("write_unittest", unittest_node)
builder.add_node("run_unittest", run_unittest_node)



builder.set_entry_point("planner")


builder.add_conditional_edges( 
    "run_unittest", 
    interactive_failing_check, 
    {True: "debugging_developer", False: "feedback_developer"}
    
)

builder.add_conditional_edges( 
    "write_unittest", 
    check_if_cpp_code_created,
    {True: "run_unittest", False: "main_developer"}
    
)


builder.add_edge("planner", "main_developer")
builder.add_edge("main_developer", "write_unittest")
#builder.add_edge("write_unittest", "run_unittest")
builder.add_edge("debugging_developer", "research_debug")
builder.add_edge("feedback_developer", "research_plan")
builder.add_edge("research_debug", "planner")
builder.add_edge("research_plan", "planner")



graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["run_unittest"]
)



print("Agent network instantiated successfully! Here's your agent's graph: ")

from IPython.display import Image

Image(graph.get_graph().draw_png())




thread = {"configurable": {"thread_id": "1"}}
for s in graph.stream({
    'task': "Create the application described!"
    
}, thread):
    print(s)