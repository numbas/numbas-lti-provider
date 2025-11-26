port module App exposing (..)

import Browser
import Browser.Dom
import Dict exposing (Dict)
import Html as H exposing (Html)
import Html.Attributes as HA
import Html.Events as HE
import Html.Keyed as HK
import Json.Decode as JD
import Json.Encode as JE
import List.Extra as LE
import Task
import Tuple exposing (pair, first, second)

ff = String.fromFloat
fi = String.fromInt
nocmd model = (model, Cmd.none)

port send_output : JE.Value -> Cmd msg

main = Browser.element
    { init = init
    , update = update
    , subscriptions = subscriptions
    , view = view
    }

type alias Model = 
  { groups : List Group
  , selected_item : Maybe Item
  , drags : List Item
  , focus_group : Maybe Int
  }

type alias Item =
  { id : String
  , label : String
  , url : String
  }

type alias Group = 
  { name : String
  , items : List Item
  , editable : Bool
  , focus_index : Int
  }

type Msg
  = ItemToGroup Item Int Int
  | AddGroup
  | DeleteGroup Int
  | SelectItem Item
  | ClickItem Item Int Int
  | StartDrag Item
  | EndDrag Item
  | NoOp
  | Drop Int Int
  | FocusGroup Int
  | BlurGroup Int
  | FocusUp
  | FocusDown
  | FocusLeft
  | FocusRight
  | SetGroupName Int String

blank_group =
  { name = ""
  , items = []
  , editable = True
  , focus_index = 0
  }

type alias LoadItem =
  { item : Item
  , order : Int
  , group_name : String
  , group_order : Int
  , selected: Bool
  }

decode_groups : JD.Decoder (List Group)
decode_groups =
  JD.list (
    JD.map5 LoadItem
      (JD.map3 Item (JD.field "pk" JD.string) (JD.field "name" JD.string) (JD.field "url" JD.string))
      (JD.field "order" JD.int)
      (JD.field "group" JD.string)
      (JD.field "group_order"
        (JD.oneOf
          [JD.int
          ,JD.succeed 0
          ]
        )
      )
      (JD.field "selected" JD.bool)
  )
  |> JD.map loaditems_to_groups

loaditems_to_groups : List LoadItem -> List Group
loaditems_to_groups loaditems =
  let
    (selected, unselected) = List.partition (.selected) loaditems
    unselected_group = { blank_group | name = "Unselected", editable = False, items = List.map (.item) unselected }

    groups = 
      selected 
      |> List.sortBy (\a -> (a.group_name, a.group_order))
      |> LE.groupWhile (\a b -> a.group_name == b.group_name && a.group_order == b.group_order)
      |> List.map (\(i1,rest) -> { blank_group | name=i1.group_name, items = List.map .item (i1::rest |> List.sortBy .order)})
  in
    unselected_group :: groups
  

init_model = 
  { groups = []
  , selected_item = Nothing
  , drags = []
  , focus_group = Nothing
  }

cyclic_name : Int -> List String -> String
cyclic_name nn words =
  let
    inner n = 
      let
        l = List.length words
        c = modBy l n
        q = (n - c) // l
        w = words |> List.drop c |> List.head |> Maybe.withDefault ""
      in
        if n == 0 then "" else (inner q)++" "++w
  in
    if nn == 0 then List.head words |> Maybe.withDefault "" else inner nn


init : JD.Value -> (Model, Cmd msg)
init flags =
  let
    groups = 
      JD.decodeValue (JD.field "items" decode_groups) flags 
      |> Result.withDefault []
  in
    { init_model | groups = groups++[blank_group] } |> nocmd

insertBefore : Int -> a -> List a -> List a
insertBefore i x list = (List.take i list)++[x]++(List.drop i list)

indexOf : a -> List a -> Maybe Int
indexOf x = List.indexedMap pair >> List.filter (second >> (==) x) >> List.map first >> List.head

remove_item : Item -> Model -> Model
remove_item item model =
  let
    filter = List.filter (.id >> (/=) item.id)
    ngroups = List.map (\g -> { g | items = filter g.items }) model.groups
  in
    { model | groups = ngroups }

update_group : (Group -> Group) -> Int -> Model -> Model
update_group fn gi model =
  let
    ngroups = LE.updateAt gi fn model.groups
  in
    { model | groups = ngroups }

add_group model = { model | groups = model.groups++[blank_group] }

id_for_item : Int -> Int -> String
id_for_item gi ni = "sortable-item-"++(fi gi)++"-"++(fi ni)

id_for_group : Int -> String
id_for_group gi = "group-name-"++(fi gi)

move_item_to_group : Item -> Int -> Int -> Model -> (Model, Cmd Msg)
move_item_to_group item gi index model =
  let
    filter = List.filter (.id >> (/=) item.id)
    
    ngroups = 
      model.groups
      |> List.indexedMap (\ggi group ->
        if ggi == gi then
          let
            ni = case (indexOf item group.items) of
              Just i -> if i < index-1 then index else index
              Nothing -> index
            
            nitems = 
              group.items 
              |> filter
              |> insertBefore ni item
          in
             { group | items = nitems, focus_index = ni }
        else
          { group | items = filter group.items }
      )
      |> List.map (\g -> { g | focus_index = clamp 0 (List.length g.items - 1) g.focus_index })
  in
    ({ model | selected_item = Nothing, groups = ngroups }
    , attempt_focus_item gi index
    )
    |> and_send_output


and_send_output (model,cmd) = (model, Cmd.batch [cmd, send_output <| encode_output model])

update msg model = case msg of
  NoOp -> model |> nocmd

  ItemToGroup item gi index -> move_item_to_group item gi index model
  
  AddGroup -> 
    ( model |> add_group
    , attempt_focus <| id_for_group <| List.length model.groups
    )
  
  DeleteGroup gi ->
    let
      items = LE.getAt gi model.groups |> Maybe.map .items |> Maybe.withDefault []
      ngroups = 
        model.groups 
        |> LE.removeAt gi
        |> LE.updateAt 0 (\g -> { g | items = g.items ++ items })
    in
      { model | groups = ngroups }
      |> nocmd
      |> and_send_output
      
  SelectItem item -> 
    let
      selected_item = if model.selected_item == Just item then Nothing else Just item
    in
      { model | selected_item = selected_item }
      |> nocmd

  ClickItem item gi ii -> 
    model 
    |> update (
        case model.selected_item of
          Just selected_item -> 
            if selected_item == item then SelectItem item
            else ItemToGroup selected_item gi ii
          Nothing -> SelectItem item
       ) 

  StartDrag item ->
    { model | drags = item::model.drags }
    |> nocmd

  EndDrag item ->
    { model | drags = List.filter ((/=) item) model.drags }
    |> nocmd

  Drop gi ii ->
    case List.head model.drags of
      Nothing -> model |> nocmd
      
      Just item -> move_item_to_group item gi ii model

  FocusGroup i -> 
    { model | focus_group = Just i }
    |> nocmd

  BlurGroup i ->
    { model | focus_group = if model.focus_group == Just i then Nothing else model.focus_group }
    |> nocmd

  FocusDown -> move_group_focus 1 model

  FocusUp -> move_group_focus -1 model

  FocusLeft -> focus_next_group -1 model

  FocusRight -> focus_next_group 1 model

  SetGroupName gi name -> 
    { model | groups = LE.updateAt gi (\g -> { g | name = name }) model.groups }
    |> nocmd
    |> and_send_output

attempt_focus id =
  Task.attempt 
    (\_ -> NoOp) 
    (Browser.Dom.focus id)

attempt_focus_item gi ii = attempt_focus <| id_for_item gi ii

move_group_focus : Int -> Model -> (Model, Cmd Msg)
move_group_focus d model = 
    case Maybe.map2 pair model.focus_group (model.focus_group |> Maybe.andThen (\gi -> LE.getAt gi model.groups)) of
      Nothing -> model |> nocmd
      Just (gi,group) ->
        let
          ni = clamp 0 (max 0 (List.length group.items - 1)) (group.focus_index + d)
          ngroups = LE.updateAt gi (\g -> { g | focus_index = ni }) model.groups
        in
          ( { model | groups = ngroups }
          , attempt_focus_item gi ni
          )

focus_next_group : Int -> Model -> (Model, Cmd Msg)
focus_next_group d model = case model.focus_group of
  Nothing -> model |> nocmd
  Just gi ->
    let
      ngi = clamp 0 (List.length model.groups - 1) (gi+d)
      ii = 
        LE.getAt ngi model.groups 
        |> Maybe.map (\g -> clamp 0 (max 0 (List.length g.items - 1)) g.focus_index)
        |> Maybe.withDefault 0
    in
      (model, attempt_focus_item ngi ii)


subscriptions model = Sub.none

droppable = HE.preventDefaultOn "dragover" <| JD.succeed (NoOp,True)

apply_keymap : Dict String Msg -> JD.Decoder Msg
apply_keymap keymap = 
  JD.field "key" JD.string
  |> JD.andThen (\key -> case (Dict.get key keymap) of
      Nothing -> JD.fail "no"
      Just msg -> JD.succeed msg
      )

view : Model -> Html Msg
view model = 
  let
    keymap spacemsg = Dict.fromList
      [ ("ArrowUp", FocusUp)
      , ("ArrowDown", FocusDown)
      , ("ArrowLeft", FocusLeft)
      , ("ArrowRight", FocusRight)
      , (" ", spacemsg)
      ]
      
    view_group : Int -> Group -> Html Msg
    view_group gi group =
      H.article
        ( [ HA.class "group"
          , droppable
          , HA.attribute "aria-labelledby" <| id_for_group gi
          , HE.on "drop" (JD.succeed (Drop gi (List.length group.items)))
          ]
        ++ (case model.selected_item of
            Just item -> [ HE.onClick <| ItemToGroup item gi (List.length group.items) ]
            _ -> []
          )
        ++ (if group.items == [] then
              [ HA.tabindex 0
              , HA.id <| id_for_item gi 0
              , HE.onFocus (FocusGroup gi)
              , HE.onBlur (BlurGroup gi)
              , keymap (case model.selected_item of
                    Nothing -> NoOp
                    Just item -> ItemToGroup item gi 0)
                |> apply_keymap 
                |> HE.on "keyup"
              ]
            else
              []
           )
        )
        [ H.header 
            [] 
            (if group.editable then 
                [ H.input 
                    [ HA.id <| id_for_group gi
                    , HA.value group.name
                    , HA.attribute "aria-label" "Group name"
                    , HE.onInput <| SetGroupName gi
                    ]
                    [] 
                , H.button
                    [ HA.type_ "button"
                    , HE.onClick <| DeleteGroup gi
                    ]
                    [ H.text "Delete" ]
                ]
              else
                [ H.text group.name ]
            )
        , HK.node "ol"
          [ HA.attribute "role" "listbox"
          ]
          (group.items |> List.indexedMap (\ii item ->
            let
              group_keypress : JD.Decoder Msg
              group_keypress = apply_keymap <| keymap (ClickItem item gi ii)

            
            in
              ( item.id
              , H.li 
                  ( [ HA.attribute "role" "option"
                    , HE.on "focusin" (JD.succeed <| FocusGroup gi)
                    , HE.on "focusout" (JD.succeed <| BlurGroup gi)
                    , HE.on "keyup" group_keypress
                    , HA.classList
                        [ ("item", True)
                        ]
                    , HA.attribute "draggable" "true"
                    , HE.on "dragstart" (JD.succeed (StartDrag item))
                    , HE.on "dragend" (JD.succeed (EndDrag item))
                    ]
                    ++ (if model.selected_item == Just item then [ HA.attribute "aria-selected" ""] else [])
                    ++ ( if List.member item model.drags then 
                           [ HA.attribute "hidden" "true" ] 
                         else 
                           [ droppable
                           , HE.stopPropagationOn "drop" <| JD.succeed (Drop gi ii, True)
                           ]
                       )
                  )
                    
                  [ H.a 
                    [ HA.href item.url
                    , HA.target "_blank"
                    , HA.tabindex <| if ii == group.focus_index then 0 else -1
                    , HA.id <| id_for_item gi ii
                    ]
                    [H.text item.label]
                  ]
              )
            ))
        ]

  in
    H.div
      [ HA.id "group-sorter" ]
      [ H.ul 
        [ HA.class "groups" ] 
        ((model.groups |> List.indexedMap view_group)
          ++
          [ H.button
            [ HA.type_ "button"
            , HE.onClick AddGroup
            ]
            [ H.text "Add a group" ]
          ]
        )
      ]


encode_output : Model -> JE.Value
encode_output model =
  model.groups
  |> List.filter (.editable)
  |> JE.list (\g -> JE.object
    [ ("name", JE.string g.name)
    , ("items", g.items |> JE.list (.id >> JE.string))
    ]
    )
